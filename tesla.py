import os
import time
import csv
import zipfile
import shutil
from packet_functions import get_value, modify_packet_value, make_new_packet

csv_path = '/home/drive_record/'

# 로그파일로 남길 메모리 주소
logging_address = ['0x108', '0x118', '0x129', '0x132', '0x186', '0x1d5', '0x1d8', '0x201', '0x20c', '0x229', '0x238',
                   '0x243', '0x249', '0x257', '0x25a', '0x261', '0x266', '0x273', '0x282', '0x292', '0x293', '0x2a7',
                   '0x2b3', '0x2d3', '0x2e1', '0x2e5', '0x2f1', '0x2f3', '0x312', '0x315', '0x318', '0x321', '0x32c',
                   '0x332', '0x334', '0x33a', '0x352', '0x353', '0x373', '0x376', '0x383', '0x39d', '0x3b6', '0x3d2',
                   '0x3d8', '0x3e2', '0x3e3', '0x3f2', '0x3f5', '0x3fd', '0x401', '0x4f', '0x528', '0x7aa', '0x7ff']

# multiplexer 적용 패킷인 경우, multiplexer 개수 정보 추가
mux_address = {'0x282': 2, '0x352': 2, '0x3fd': 3, '0x332': 2, '0x261': 2, '0x243': 3, '0x7ff': 8, '0x2e1': 3,
               '0x201': 3, '0x7aa': 4, '0x2b3': 4, '0x3f2': 4, '0x32c': 8, '0x401': 8}

command = {
    'volume_down': bytes.fromhex('2955010000000000'),
    'volume_up': bytes.fromhex('29553f0000000000'),
    'speed_down': bytes.fromhex('2955003f00000000'),
    'speed_up': bytes.fromhex('2955000100000000'),
}


class Buffer:
    def __init__(self):
        self.logging_address = [int(x, 16) for x in logging_address]
        self.mux_address = mux_address
        self.can_buffer = {}
        self.message_buffer = []
        self.initial_can_buffer()

    def initial_can_buffer(self):
        self.can_buffer = {0: {x: {0: None} for x in self.logging_address}}
        for m_address, byte in self.mux_address.items():
            for i in range(2 ** byte):
                self.can_buffer[0][int(m_address, 16)][i] = None

    def flush_message_buffer(self):
        self.message_buffer = []

    def write_can_buffer(self, bus: int, address: int, signal: bytes):
        if hex(address) in self.mux_address.keys():
            mux = signal[0] & (2 ** self.mux_address[hex(address)] - 1)
        else:
            mux = 0
        if self.can_buffer[bus].get(address):
            self.can_buffer[bus][address][mux] = signal

    def write_message_buffer(self, bus, address, signal):
        self.message_buffer.append([bus, address, signal])


class Dashboard:
    def __init__(self):
        self.drive_start_time = 0
        self.last_update = 0
        self.unix_time = 0
        self.clock = None
        self.parked = 1
        self.gear = 0
        self.accel_pedal_pos = 0
        self.drive_mode = 0
        self.ui_speed = 0
        self.torque_front = 0
        self.torque_rear = 0
        self.LVB_voltage = 0
        self.soc = 0
        self.ui_range = 0
        self.HVB_max_temp = 0
        self.HVB_min_temp = 0
        self.nominal_full = 0
        self.device_temp = 0
        self.fresh_request = 0
        self.autopilot = 0
        self.nag_disabled = 0
        self.recirc_mode = 0  # 0 Auto, 1 내기, 2 외기
        self.passenger = [0, 0, 0, 0, 0]  # fl, fr, rl, rc, rr
        self.passenger_cnt = 0
        self.wiper_state = 0
        self.wiper_off_request = 0
        self.mirror_folded = [0, 0]  # folded 1, unfolded 0

    def update(self, name, signal):
        if name == 'UnixTime':
            self.unix_time = int.from_bytes(signal, byteorder='big')
            self.clock = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.unix_time))
        elif name == 'DriveSystemStatus':
            self.gear = get_value(signal, 21, 3)
            self.accel_pedal_pos = get_value(signal, 32, 8) * 0.4
        elif name == 'UI_powertrainControl':
            self.pedal_map = get_value(signal, 5, 2)  # 0 Comport, 1 Sport 2 Performance
        elif name == 'DIspeed':
            self.ui_speed = max(0, get_value(signal, 24, 9))
        elif name == 'DIR_torque':
            self.torque_rear = get_value(signal, 27, 13, signed=True) * 2
        elif name == 'DIF_torque':
            self.torque_front = get_value(signal, 27, 13, signed=True) * 2
        elif name == '12vBattStatus':
            mux = get_value(signal, 0, 3)
            if mux == 1:
                self.LVB_voltage = get_value(signal, 32, 12) * 0.00544368
        elif name == 'BMS_SOC':
            self.soc = get_value(signal, 10, 10) * 0.1
        elif name == 'UI_rangeSOC':
            self.ui_range = int(get_value(signal, 0, 10) * 1.6)
        elif name == 'BMS_energyStatus':
            self.nominal_full = get_value(signal, 0, 11) * 0.1
        elif name == 'BMSthermal':
            self.HVB_max_temp = get_value(signal, 53, 9) * 0.25 - 25
            self.HVB_min_temp = get_value(signal, 44, 9) * 0.25 - 25
        elif name == 'UI_hvacRequest':
            self.recirc_mode = get_value(signal, 20, 2)
        elif name == 'VCLEFT_switchStatus':
            mux = get_value(signal, 0, 2)
            if mux == 0:
                self.passenger[0] = 1 if get_value(signal, 50, 2) == 2 else 0  # front left, occupancy
                self.passenger[2] = 1 if get_value(signal, 56, 2) == 2 else 0  # rear left, occupancy
                self.passenger[3] = 1 if get_value(signal, 54, 2) == 2 else 0  # rear center, occupancy
                self.passenger[4] = 1 if get_value(signal, 58, 2) == 2 else 0  # rear right, occupancy
                self.passenger_cnt = sum(self.passenger)
        elif name == 'VCRIGHT_switchStatus':
            mux = get_value(signal, 0, 2)
            if mux == 0:
                self.passenger[1] = 1 if get_value(signal, 40, 2, 'little') == 2 else 0  # front right, belt
                self.passenger_cnt = sum(self.passenger)
        elif name == 'UI_vehicleControl':
            self.wiper_state = get_value(signal, 56, 3)
        elif name == 'VCLEFT_doorStatus':
            state = get_value(signal, 52, 3)
            if state in [2, 4]:
                self.mirror_folded[0] = 0
            elif state in [1, 3]:
                self.mirror_folded[0] = 1
        elif name == 'VCRIGHT_doorStatus':
            state = get_value(signal, 52, 3)
            if state in [2, 4]:
                self.mirror_folded[1] = 0
            elif state in [1, 3]:
                self.mirror_folded[1] = 1


class WelcomeVolume:
    def __init__(self, sender, device='raspi'):
        self.sender = sender
        if device == 'panda':
            self.device = 'panda'
            self.tx_frame = None
        elif device == 'raspi' and type(sender) == list:
            self.device == 'raspi'
            self.sender = sender[0]
            self.tx_frame = sender[1]
            self.tx_frame.arbitration_id = 0x3c2
            self.tx_frame.is_extended_id = False
        else:
            self.device = None

    def run(self):
        if self.device == 'panda':
            self.sender.can_send(0x3c2, command['volume_up'], 0)
            time.sleep(0.5)
            self.sender.can_send(0x3c2, command['volume_down'], 0)
            time.sleep(0.5)
        elif self.device == 'raspi':
            self.tx_frame.data = list(bytearray(command['volume_down']))
            self.sender.send(self.tx_frame)
            time.sleep(0.5)
            self.tx_frame.data = list(bytearray(command['volume_up']))
            self.sender.send(self.tx_frame)
            time.sleep(0.5)
        else:
            pass


class Logger:
    def __init__(self, buffer, dash, cloud=0):
        # 클라우드 업로드용은 7zip 알고리즘을 사용하여 용량을 대폭 줄일 수 있으나, 일부 압축프로그램에서 열리지 않음
        self.buffer = buffer
        self.dash = dash
        self.cloud = cloud
        self.filename = None
        self.file = None
        self.csvwriter = None

    def initialize(self):
        if not os.path.exists(csv_path):
            os.makedirs(csv_path)
        if self.cloud == 1 and not os.path.exists(csv_path + 'sync/'):
            os.makedirs(csv_path + 'sync/')

        self.filename = time.strftime('DLOG_%y%m%d_%H%M%S.csv', time.localtime(self.dash.unix_time))
        self.file = open(csv_path + self.filename, 'w', newline='')
        self.csvwriter = csv.writer(self.file)
        self.csvwriter.writerow(['Time', 'Bus', 'MessageID', 'Multiplexer', 'Message'])

    def close(self):
        if self.file is None:
            #            print('Need Initialize')
            return False
        if not self.file.closed:
            self.file.close()
            zip_filename = self.filename.split('.')[0] + '.zip'
            if self.cloud:
                with zipfile.ZipFile(csv_path + zip_filename, 'w', zipfile.ZIP_LZMA) as myzip:
                    myzip.write(csv_path + self.filename, arcname=self.filename)
                shutil.move(csv_path + zip_filename, csv_path + 'sync/' + zip_filename)
                os.remove(csv_path + self.filename)
            else:
                with zipfile.ZipFile(csv_path + zip_filename, 'w', zipfile.ZIP_DEFLATED) as myzip:
                    myzip.write(csv_path + self.filename, arcname=self.filename)

    def write(self):
        if self.file is None:
            print('Need Initialize')
            return False
        if (not self.file.closed) and (self.csvwriter is not None):
            # Logging signal every second
            for address in self.buffer.can_buffer[0]:
                for mux, signal in self.buffer.can_buffer[0][address].items():
                    if signal is not None:
                        self.csvwriter.writerow([self.dash.clock, 0, str(hex(address)), mux, '0x' + str(signal.hex())])


class MapLampControl:
    def __init__(self, buffer, dash, sender=None, device='raspi'):
        self.buffer = buffer
        self.dash = dash
        self.device = device
        self.sender = sender
        self.left_map_light_pressed = 0
        self.right_map_light_pressed = 0
        self.left_map_light_first_pressed_time = 0
        self.right_map_light_first_pressed_time = 0
        self.mirror_request = 0 # 0 중립, 1 접기 2 펴기
        self.mirror_folded = 0
        self.fold_request_time = None

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x3e2):
            # Check Left Map Light Long Pressed
            if get_value(byte_data, 14, 1) == 1:
                if self.left_map_light_pressed == 0:
                    self.left_map_light_first_pressed_time = time.time()
                    self.left_map_light_pressed = 1
                if (self.left_map_light_first_pressed_time != 0) and (
                        time.time() - self.left_map_light_first_pressed_time >= 1):
                    self.left_map_light_switch_long_pressed()
                    self.left_map_light_first_pressed_time = 0
            else:
                self.left_map_light_pressed = 0
                self.left_map_light_first_pressed_time = 0

            # Check Right Map Light Long Pressed
            if get_value(byte_data, 15, 1) == 1:
                if self.right_map_light_pressed == 0:
                    self.right_map_light_first_pressed_time = time.time()
                    self.right_map_light_pressed = 1
                if (self.right_map_light_first_pressed_time != 0) and (
                        time.time() - self.right_map_light_first_pressed_time >= 1):
                    self.right_map_light_switch_long_pressed()
                    self.right_map_light_first_pressed_time = 0
            else:
                self.right_map_light_pressed = 0
                self.right_map_light_first_pressed_time = 0

        if (bus == 0) and (address == 0x273):
            if self.mirror_request in [1, 2]:
                ret = modify_packet_value(byte_data, 24, 2, self.mirror_request)
                self.buffer.write_message_buffer(0, 0x273, ret)
            if self.fold_request_time is None:
                self.fold_request_time = time.time()
            elif (time.time() - self.fold_request_time) > 1:
                self.mirror_request = 0
                self.fold_request_time = None

    def mirror_fold(self):
        if self.dash.mirror_folded[0] == 1 or self.dash.mirror_folded[1] == 1:
            self.mirror_request = 1
        else:
            self.mirror_request = -1

    def left_map_light_switch_long_pressed(self):
        print('Left Map Switch Pressed over 1 second')
        self.mirror_fold()

    def right_map_light_switch_long_pressed(self):
        print('Right Map Switch Pressed over 1 second')
        # 현재 사용하지 않는 예비 기능


class Autopilot:
    def __init__(self, buffer, dash, sender=None, device='raspi'):
        self.timer = 0
        self.buffer = buffer
        self.dash = dash
        self.tacc = 0
        self.autosteer = 0
        self.last_gear_position = 0
        self.gear_down_pressed = 0
        self.gear_pressed_time = 0
        self.first_down_time = 0
        self.nag_disabled = 0
        self.mars_mode = 0
        if sender:
            self.welcome = WelcomeVolume(sender, device)
        else:
            self.welcome = None
        self.wiper_mode_rollback_request = 0
        self.wiper_last_state = 0

    def disable_nag(self):
        self.mars_mode = 1

    def run(self):
        # from Spleck's github (https://github.com/spleck/panda)
        # 운전 중 스티어링 휠을 잡고 정확히 조향하는 것은 운전자의 의무입니다.
        # 미국 생산 차량에서만 다이얼을 이용한 NAG 제거가 유효하며, 중국 생산차량은 적용되지 않습니다.
        if (self.mars_mode) and (self.autosteer == 1) and (self.nag_disabled == 1):
            self.timer += 1
            if self.timer == 6:
                print('Right Scroll Wheel Down')
                self.buffer.write_message_buffer(0, 0x3c2, command['speed_down'])
            elif self.timer >= 7:
                print('Right Scroll Wheel Up')
                self.buffer.write_message_buffer(0, 0x3c2, command['speed_up'])
                self.timer = 0

    def disengage_autopilot(self):
        print('Autopilot Disengaged')
        self.tacc = 0
        self.autosteer = 0
        self.dash.autopilot = 0
        self.first_down_time = 0
        self.gear_down_pressed = 0
        self.nag_disabled = 0
        self.dash.nag_disabled = 0
        print('NAG Eliminator Deactivated')
        if self.dash.wiper_state != 2:
            self.wiper_mode_rollback_request = 0

    def engage_autopilot(self):
        self.tacc = 0
        self.autosteer = 1
        self.dash.autopilot = 1
        self.first_down_time = 0
        self.gear_down_pressed = 0
        self.timer = 0

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x39d):
            if (self.mars_mode) and (self.autosteer):
                brake_switch = get_value(byte_data, 16, 2)
                if brake_switch == 2:
                    self.disengage_autopilot()

        if (bus == 0) and (address == 0x273):
            # 마지막 와이퍼 상태 유지 기능 - 아직 테스트 중
            if self.wiper_mode_rollback_request == 1:
                ret = modify_packet_value(byte_data, 56, 3, self.wiper_last_state)
                self.buffer.write_message_buffer(0, 0x273, ret)

        if (bus == 0) and (address == 0x229) and (self.dash.gear == 4):
            # 기어 스토크 상태 체크
            self.gear_pressed_time = time.time()
            gear_position = get_value(byte_data, 12, 3)
            if gear_position in [1, 2]:
                self.disengage_autopilot()
            elif gear_position in [3, 4]:
                if self.autosteer == 0 and self.last_gear_position == 0:
                    if self.gear_down_pressed == 0:
                        self.gear_down_pressed = 1
                        self.tacc = 1
                        self.wiper_mode_rollback_request = 1
                        self.first_down_time = self.gear_pressed_time
                    elif self.gear_down_pressed == 1:
                        gear_press_gap = (self.gear_pressed_time - self.first_down_time)
                        if gear_press_gap < 1:
                            print('Autopilot Engaged')
                            self.engage_autopilot()
                        else:
                            self.first_down_time = self.gear_pressed_time
                if gear_position == 4 and self.autosteer == 1 and self.nag_disabled == 0:
                    self.nag_disabled = 1
                    self.dash.nag_disabled = 1
                    print('NAG Eliminator Activated')
                    self.welcome.run()
            elif gear_position == 0:
                if (self.autosteer == 0) and (self.first_down_time != 0) and (
                        time.time() - self.gear_pressed_time) >= 1:
                    self.first_down_time = 0
                    self.gear_down_pressed = 0

                if (self.wiper_last_state != self.dash.wiper_state):
                    # 오토파일럿 시 와이퍼 상태 유지시키기 위해, 마지막 상태를 기억한다.
                    if (self.dash.wiper_state != 2):
                        self.wiper_last_state = self.dash.wiper_state
                    elif self.tacc or self.autosteer:
                        if time.time() - self.gear_pressed_time > 1:
                            self.wiper_last_state = self.dash.wiper_state

            self.last_gear_position = gear_position


class RearCenterBuckle:
    def __init__(self, buffer):
        self.buffer = buffer

    def modulate(self, bus, address, byte_data):
        mux = get_value(byte_data, loc=0, length=2, endian='little', signed=False)
        if mux == 0:
            # 뒷좌석 가운데자리 착좌센서 끄고, 안전벨트 스위치 켜기
            ret_data = modify_packet_value(byte_data, 54, 2, 1)
            ret_data = modify_packet_value(ret_data, 62, 2, 2)

            # 뒷좌석 안전벨트 미착용 상태로 승객을 태우는 것은 매우 위험하며, 도로교통법 위반입니다.
            # 짐을 쌓은 상태로 부득이 정리가 어려운 경우에만 사용하세요.
            # Disable rearLeftOccupancySwitch
            # ret_data = modify_packet_value(byte_data, 56, 2, 1)
            # Disable rearRightOccupancySwitch
            # ret_data = modify_packet_value(byte_data, 58, 2, 1)
            self.buffer.write_message_buffer(bus, address, ret_data)


class FreshAir:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash
        self.mode_value = 1
        # 마지막으로 Frseh로 바뀐 시간, 마지막으로 Recirc로 바뀐 시간
        self.last_mode_change = time.time()
        # n명 탑승 시 (a분 내기, b분 외기)
        self.time_dict = {1: (10, 5),
                          2: (7, 8),
                          3: (5, 10),
                          4: (0, 1440),
                          5: (0, 1440)}

    def check(self, bus, address, byte_data):
        if (self.dash.passenger_cnt == 0):
            # 차 기본값 동작하도록
            return
        if (bus == 0) and (address == 0x2f3):
            if self.dash.recirc_mode != 0:
                # UI에서 Auto로 설정되어 있는 경우에만 자동 조작
                return
        else:
            return

        recirc_time, fresh_time = self.time_dict[self.dash.passenger_cnt]
        now = time.time()
        elapsed = (now - self.last_mode_change)

        if (self.mode_value == 1) and (elapsed > (60 * recirc_time)):
            # 내기 모드로 지정 시간을 넘었을 때
            self.mode_value = 2
            self.last_mode_change = now
        elif (self.mode_value == 2) and (elapsed > (60 * fresh_time)):
            # 외기 모드로 지정 시간을 넘었을 때
            self.mode_value = 1
            self.last_mode_change = now

        self.buffer.write_message_buffer(bus, address, modify_packet_value(byte_data, 20, 2, self.mode_value))


class KickDown:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash
        self.enabled = 0

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x39d):
            if self.enabled:
                brake_switch = get_value(byte_data, 16, 2)
                if brake_switch == 2:
                    print('Brake Pressed, Kick Down mode disabled')
                    self.enabled = 0

        if (bus == 0) and (address == 0x334):
            if (self.dash.drive_mode == 0) and (self.dash.accel_pedal_pos > 90) and (not self.enabled):
                print('------- Kick Down / Sports Mode On -------')
                self.enabled = 1
            if self.enabled:
                ret = make_new_packet(0x334, byte_data, [(5, 2, 1)])
                self.buffer.write_message_buffer(bus, address, ret)
