import argparse
import csv
import json
import os
import signal
import time
from collections import defaultdict
from datetime import datetime

from functions import initialize_canbus_connection


READ_ONLY = True


class DbcCatalog:
    def __init__(self, dbc_path):
        self.dbc_path = dbc_path
        self.message_map = {}  # frame_id -> {'name': str, 'signals': [str]}
        self.chassis_ids = set()
        self._load_from_dbc()

    def _load_from_dbc(self):
        if not os.path.exists(self.dbc_path):
            raise FileNotFoundError(f'DBC file not found: {self.dbc_path}')

        current_id = None
        with open(self.dbc_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('BO_ '):
                    # BO_ <id> <name>: <dlc> <sender_node>
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            frame_id = int(parts[1])
                        except ValueError:
                            current_id = None
                            continue
                        message_name = parts[2].replace(':', '')
                        sender_node = parts[-1]

                        self.message_map[frame_id] = {
                            'name': message_name,
                            'signals': []
                        }
                        current_id = frame_id

                        # chassis-only dbc여도 호환성을 위해 sender_node 확인 유지
                        if sender_node == 'ChassisBus':
                            self.chassis_ids.add(frame_id)
                    else:
                        current_id = None

                elif line.startswith('SG_ ') and current_id is not None:
                    # SG_ <signal_name> ...
                    # SG_ m0 SignalName ... 형태도 지원
                    body = line[4:]
                    if ':' not in body:
                        continue
                    left = body.split(':', 1)[0].strip()
                    left_parts = left.split()
                    if not left_parts:
                        continue
                    signal_name = left_parts[-1]
                    self.message_map[current_id]['signals'].append(signal_name)

        # chassis-only 고정 파일인데 sender_node가 비어있거나 다를 경우를 대비
        if not self.chassis_ids:
            self.chassis_ids = set(self.message_map.keys())


class DbcDecoder:
    def __init__(self, dbc_path):
        self.enabled = False
        self.db = None
        try:
            import cantools
            self.db = cantools.database.load_file(dbc_path)
            self.enabled = True
        except Exception as e:
            print(f'cantools decode disabled: {e}')

    def decode(self, frame_id, data):
        if not self.enabled:
            return ''
        try:
            message = self.db.get_message_by_frame_id(frame_id)
            if message is None:
                return ''
            decoded = message.decode(bytes(data), decode_choices=True)
            return json.dumps(decoded, ensure_ascii=False, separators=(',', ':'))
        except Exception:
            return ''


class ChassisCollector:
    def __init__(self, catalog, decoder, out_dir):
        self.catalog = catalog
        self.decoder = decoder
        self.out_dir = out_dir

        self.total_received = 0
        self.hourly_counts = defaultdict(int)  # (hour_bucket, frame_id) -> count
        self.addr_summary = {}  # frame_id -> dict
        self.addr_rows = defaultdict(list)  # frame_id -> [row dict]

    def consume(self, msg):
        frame_id = msg.arbitration_id
        if frame_id not in self.catalog.chassis_ids:
            return

        ts = msg.timestamp if msg.timestamp else time.time()
        dt = datetime.fromtimestamp(ts)
        hour_bucket = dt.strftime('%Y-%m-%d %H:00:00')
        ts_local = dt.strftime('%Y-%m-%d %H:%M:%S')

        self.total_received += 1
        self.hourly_counts[(hour_bucket, frame_id)] += 1

        entry = self.addr_summary.get(frame_id)
        if entry is None:
            entry = {
                'count': 0,
                'first_seen': ts,
                'last_seen': ts,
                'dlc_set': set(),
            }
            self.addr_summary[frame_id] = entry

        entry['count'] += 1
        if ts < entry['first_seen']:
            entry['first_seen'] = ts
        if ts > entry['last_seen']:
            entry['last_seen'] = ts
        entry['dlc_set'].add(len(msg.data))

        message_info = self.catalog.message_map.get(frame_id, {})
        signal_names = message_info.get('signals', [])
        decoded_json = self.decoder.decode(frame_id, msg.data)

        self.addr_rows[frame_id].append({
            'ts_unix': f'{ts:.6f}',
            'ts_local': ts_local,
            'can_id_hex': f'0x{frame_id:03X}',
            'message_name': message_info.get('name', ''),
            'dlc': len(msg.data),
            'data_hex': msg.data.hex(),
            'signal_names': ','.join(signal_names),
            'signal_json': decoded_json,
        })

    def export_all(self):
        os.makedirs(self.out_dir, exist_ok=True)

        self._export_hourly_summary()
        self._export_addr_summary()
        self._export_addr_details()

    def _export_hourly_summary(self):
        path = os.path.join(self.out_dir, 'hourly_summary.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['hour_bucket', 'can_id_hex', 'message_count'])
            for (hour_bucket, frame_id), count in sorted(self.hourly_counts.items()):
                writer.writerow([hour_bucket, f'0x{frame_id:03X}', count])

    def _export_addr_summary(self):
        path = os.path.join(self.out_dir, 'addr_summary.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['can_id_hex', 'message_name', 'total_count', 'first_seen', 'last_seen', 'dlc_set'])
            for frame_id in sorted(self.addr_summary.keys()):
                item = self.addr_summary[frame_id]
                message_name = self.catalog.message_map.get(frame_id, {}).get('name', '')
                writer.writerow([
                    f'0x{frame_id:03X}',
                    message_name,
                    item['count'],
                    datetime.fromtimestamp(item['first_seen']).strftime('%Y-%m-%d %H:%M:%S'),
                    datetime.fromtimestamp(item['last_seen']).strftime('%Y-%m-%d %H:%M:%S'),
                    ','.join(str(x) for x in sorted(item['dlc_set'])),
                ])

    def _export_addr_details(self):
        for frame_id in sorted(self.addr_rows.keys()):
            path = os.path.join(self.out_dir, f'addr_0x{frame_id:03X}.csv')
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'ts_unix',
                    'ts_local',
                    'can_id_hex',
                    'message_name',
                    'dlc',
                    'data_hex',
                    'signal_names',
                    'signal_json',
                ])
                for row in self.addr_rows[frame_id]:
                    writer.writerow([
                        row['ts_unix'],
                        row['ts_local'],
                        row['can_id_hex'],
                        row['message_name'],
                        row['dlc'],
                        row['data_hex'],
                        row['signal_names'],
                        row['signal_json'],
                    ])


class ChassisListener:
    def __init__(self, args):
        self.args = args
        self.stop_requested = False

        self.catalog = DbcCatalog(args.dbc)
        self.decoder = DbcDecoder(args.dbc)
        self.collector = ChassisCollector(self.catalog, self.decoder, args.out)

        self.start_time = 0
        self.bus = None
        self.exported = False

    def request_stop(self, reason=''):
        if not self.stop_requested:
            self.stop_requested = True
            if reason:
                print(f'[STOP] {reason}')

    def run(self):
        if not READ_ONLY:
            raise RuntimeError('READ_ONLY must be True')
        try:
            import can
        except Exception as e:
            raise RuntimeError(f'python-can module is required: {e}')

        initialize_canbus_connection()
        self.bus = can.interface.Bus(channel=self.args.channel, interface='socketcan')

        print(f'[START] channel={self.args.channel} duration={self.args.duration}s out={self.args.out}')
        print(f'[DBC] chassis ids loaded: {len(self.catalog.chassis_ids)}')
        sample = sorted(list(self.catalog.chassis_ids))[:20]
        print('[DBC] sample ids:', ', '.join(f'0x{x:03X}' for x in sample))

        self.start_time = time.time()
        next_status = self.start_time + 5

        while not self.stop_requested:
            now = time.time()
            if now - self.start_time >= self.args.duration:
                self.request_stop('duration reached')
                break

            if self.args.stop_file and os.path.exists(self.args.stop_file):
                self.request_stop(f'stop-file detected: {self.args.stop_file}')
                break

            try:
                msg = self.bus.recv(timeout=0.2)
            except Exception as e:
                print(f'[ERROR] recv failed: {e}')
                self.request_stop('recv failed')
                break

            if msg is not None:
                self.collector.consume(msg)

            if now >= next_status:
                print(f'[STAT] total={self.collector.total_received}')
                next_status = now + 5

        self.shutdown()

    def shutdown(self):
        if self.exported:
            return
        self.exported = True
        print('[SAVE] exporting csv...')
        self.collector.export_all()
        print(f'[DONE] total chassis frames: {self.collector.total_received}')


def parse_args():
    parser = argparse.ArgumentParser(description='Chassis CAN read-only listener')
    parser.add_argument('--channel', default='can0', help='socketcan channel (default: can0)')
    parser.add_argument('--duration', type=int, default=600, help='capture seconds (default: 600)')
    parser.add_argument('--out', default='/home/chassis_record', help='output directory')
    parser.add_argument('--dbc', default='/home/jupiter/dbc/chassis_only.dbc', help='fixed chassis-only dbc path')
    parser.add_argument('--stop-file', default='', help='safe stop trigger file path')
    return parser.parse_args()


def main():
    args = parse_args()
    listener = ChassisListener(args)

    def _sigint_handler(sig, frame):
        listener.request_stop('SIGINT received')

    signal.signal(signal.SIGINT, _sigint_handler)
    signal.signal(signal.SIGTERM, _sigint_handler)

    try:
        listener.run()
    finally:
        # 예외 발생 시에도 가능한 저장 시도
        if not listener.stop_requested:
            listener.request_stop('finalize')
        listener.shutdown()


if __name__ == '__main__':
    main()
