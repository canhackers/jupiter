import asyncio
import threading
import os
from bleak import BleakScanner, BleakClient

beacon_keyword = 'Holy-IOT'
filename = '/home/beacons'

async def scan_beacons(name, max_retries=5, retry_delay=5):
    address = []
    for attempt in range(max_retries):
        try:
            print(f"Scanning attempt {attempt + 1}...")
            devices = await BleakScanner.discover(timeout=10.0)  # 타임아웃을 10초로 설정
            found = False
            for device in devices:
                if device and device.name and name in device.name:
                    print(f"Device {device.name}: {device.address}")
                    address.append(device.address)
                    found = True
            if found:
                break  # 장치를 찾으면 스캔 종료
        except Exception as e:
            print(f"Error during scanning: {e}")
        print(f"Retrying in {retry_delay} seconds...")
        await asyncio.sleep(retry_delay)  # 재시도 전에 기다림
    if not address:
        print("No beacons found after multiple retries.")
    return address

async def list_characteristics(address):
    try:
        async with BleakClient(address) as client:
            await client.connect()  # 연결 시도
            for service in client.services:
                if 'UART Service' in service.description:
                    for c in service.characteristics:
                        if 'UART TX' in c.description:
                            return c.uuid
        print(f"No suitable characteristics found for device: {address}")
    except Exception as e:
        print(f"Error during characteristic listing for {address}: {e}")
    return None

class HolyIoT(threading.Thread):
    def __init__(self, dash):
        super().__init__()
        self.dash = dash
        self.uuids = []
        self.thread_online = True
        self.loop = asyncio.new_event_loop()

    def notification_handler(self, sender, data, bid):
        if data[-1] == 0:
            print(f'{bid} button released')
            self.dash.beacon[bid] = 0
        if data[-1] == 1:
            print(f'{bid} button pressed')
            self.dash.beacon[bid] = 1

    async def monitor_button(self):
        while self.thread_online:
            await asyncio.sleep(1)  # 1초 간격으로 상태를 체크

    async def monitor_beacon(self, bid, mac, uuid):
        print(mac, '모니터링')
        try:
            async with BleakClient(mac) as client:
                await client.start_notify(uuid, lambda sender, data: self.notification_handler(sender, data, bid))
                await self.monitor_button()
        except Exception as e:
            print(f"Error monitoring beacon {bid}: {e}")

    async def main(self):
        self.uuids = await self.get_uuids()  # get_uuids에서 await 사용
        if not self.uuids:
            print("No beacons to monitor, stopping.")
            return
        if self.dash is not None:
            tasks = [asyncio.create_task(self.monitor_beacon(bid, mac, uuid)) for (bid, mac, uuid) in self.uuids]
            print(f'Beacons Ready to Listen')
            await asyncio.gather(*tasks, return_exceptions=True)  # 비콘을 병렬로 모니터링, 예외 처리 추가

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.main())
        self.loop.run_forever()

    def stop(self):
        self.thread_online = False
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def get_uuids(self):
        registered_beacons = {}

        candidate = []

        print('Loading saved beacon addresses...')
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    bid, addr, uuid = line.split(',')
                    candidate.append([bid.strip(), addr.strip(), uuid.strip()])

            print('disconnect exist beacon connections to make new connections...')
            for (bid, addr, uuid) in candidate:
                os.system(f"echo 'disconnect {addr}' | bluetoothctl")
                await asyncio.sleep(1)

        except Exception as e:
            print('Error while loading beacons', e)

        print('Searching available beacons...')
        available_beacons = await scan_beacons(beacon_keyword)

        for (bid, addr, uuid) in candidate:
            if addr in available_beacons:
                print(f'ID: {bid} beacon MAC: {addr} UUID: {uuid} registered')
                registered_beacons[bid] = (addr, uuid)

        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                print('Save available beacon info ...')
                for idx, mac in enumerate(available_beacons):
                    uuid = await list_characteristics(mac)
                    if uuid:
                        f.write(f'{idx + 1}, {mac}, {uuid}\n')
                    else:
                        print(f"Failed to retrieve characteristics for {mac}.")

        UUIDs = []
        if self.dash is not None:
            self.dash.beacon = {}
        for bid, (addr, uuid) in registered_beacons.items():
            UUIDs.append((bid, addr, uuid))
            if self.dash is not None:
                self.dash.beacon[bid] = 0

        return UUIDs

if __name__ == '__main__':
    HOLY = HolyIoT(None)
    HOLY.start()
