import os
import time
import can
import csv
import zipfile
import shutil
from collections import deque
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
    'empty': bytes.fromhex('2955000000000000'),
    'volume_down': bytes.fromhex('2955010000000000'),
    'volume_up': bytes.fromhex('29553f0000000000'),
    'speed_down': bytes.fromhex('2955003f00000000'),
    'speed_up': bytes.fromhex('2955000100000000'),
    'distance_far': bytes.fromhex('2956000000000000'),
    'distance_near': bytes.fromhex('2959000000000000'),
    'door_open_fl': bytes.fromhex('6000000000000000'),
    'door_open_fr': bytes.fromhex('0003000000000000'),
    'door_open_rl': bytes.fromhex('0018000000000000'),
    'door_open_rr': bytes.fromhex('00c0000000000000'),
}

# 상시 모니터링 할 주요 차량정보 접근 주소
monitoring_addrs = {0x102: 'VCLEFT_doorStatus',
                    0x103: 'VCRIGHT_doorStatus',
                    0x108: 'DIR_torque',
                    0x118: 'DriveSystemStatus',
                    0x186: 'DIF_torque',
                    0x257: 'DIspeed',
                    0x261: '12vBattStatus',
                    0x273: 'UI_vehicleControl',
                    0x292: 'BMS_SOC',
                    0x2f3: 'UI_hvacRequest',
                    0x312: 'BMSthermal',
                    0x33a: 'UI_rangeSOC',
                    0x334: 'UI_powertrainControl',
                    0x352: 'BMS_energyStatus',
                    0x3c2: 'VCLEFT_switchStatus',
                    0x31a: 'VCRIGHT_switchStatus',
                    0x528: 'UnixTime',
                    }


class Reboot:
    def __init__(self, dash):
        self.dash = dash
        self.last_pressed = 0
        self.requested = 0

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x3c2):
            mux = get_value(byte_data, 0, 2)
            if mux == 1:
                left_clicked = get_value(byte_data, 5, 2)
                right_clicked = get_value(byte_data, 12, 2)
                if left_clicked == 2 and right_clicked == 2:
                    if self.requested == 0:
                        self.requested = 1
                        print('Reboot Request counted')
                        self.last_pressed = time.time()
                    else:
                        if time.time() - self.last_pressed >= 1:
                            print('Reboot Request')
                            time.sleep(2)
                            os.system('sudo reboot')
                else:
                    self.requested = 0


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
        self.bus_error_cout = 0
        self.current_time = 0
        self.drive_start_time = 0
        self.last_update = 0
        self.unix_time = 0
        self.clock = None
        self.parked = 1
        self.gear = 0
        self.accel_pedal_pos = 0
        self.drive_mode = 0
        self.pedal_map = 0
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
        self.tacc = 0
        self.autopilot = 0
        self.nag_disabled = 0
        self.recirc_mode = 0  # 0 Auto, 1 내기, 2 외기
        self.passenger = [0, 0, 0, 0, 0]  # fl, fr, rl, rc, rr
        self.occupancy = 1
        self.occupancy_timer = 0
        self.passenger_cnt = 0
        self.wiper_state = 0
        self.wiper_off_request = 0
        self.mirror_folded = [0, 0]  # folded 1, unfolded 0
        self.navdy_connected = 0
        self.beacon = {}

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

        if self.passenger_cnt > 0:
            if self.occupancy == 0:
                self.occupancy_timer = time.time()
                self.occupancy = 1
        else:
            if (self.occupancy == 1):
                if time.time() - self.occupancy_timer > 10:
                    self.occupancy = 0


class Logger:
    def __init__(self, buffer, dash, cloud=0, enabled=0):
        # 클라우드 업로드용은 7zip 알고리즘을 사용하여 용량을 대폭 줄일 수 있으나, 일부 압축프로그램에서 열리지 않음
        self.buffer = buffer
        self.dash = dash
        self.cloud = cloud
        self.filename = None
        self.file = None
        self.csvwriter = None
        self.enabled = enabled

    def initialize(self):
        if self.enabled == 0:
            return False
        if not os.path.exists(csv_path):
            os.makedirs(csv_path)
        if self.cloud == 1 and not os.path.exists(csv_path + 'sync/'):
            os.makedirs(csv_path + 'sync/')

        self.filename = time.strftime('DLOG_%y%m%d_%H%M%S.csv', time.localtime(self.dash.unix_time))
        self.file = open(csv_path + self.filename, 'w', newline='')
        self.csvwriter = csv.writer(self.file)
        self.csvwriter.writerow(['Time', 'Bus', 'MessageID', 'Multiplexer', 'Message'])

    def close(self):
        if self.enabled == 0:
            return False
        if self.file is None:
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
        if self.enabled == 0:
            return False
        if self.file is None:
            print('Need Initialize')
            return False
        if (not self.file.closed) and (self.csvwriter is not None):
            # Logging signal every second
            for address in self.buffer.can_buffer[0]:
                for mux, signal in self.buffer.can_buffer[0][address].items():
                    if signal is not None:
                        self.csvwriter.writerow([self.dash.clock, 0, str(hex(address)), mux, '0x' + str(signal.hex())])


class Button:
    def __init__(self, btn_name):
        self.name = btn_name
        self.pressed = 0
        self.first_pressed_time = 0
        self.function = {'short': lambda *args, **kwargs: None,
                         'long': lambda *args, **kwargs: None,
                         'double': lambda *args, **kwargs: None}

    def action(self, period, args=None):
        if args:
            self.function[period](*args)
        else:
            self.function[period]()

    def press(self):
        if self.pressed == 0:
            self.first_pressed_time = time.time()
            self.pressed = 1
        if (self.first_pressed_time != 0) and (
                time.time() - self.first_pressed_time >= 1):
            print(f'{self.name} pressed over 1 second')
            self.action('long')
            self.first_pressed_time = 0

    def release(self):
        self.pressed = 0
        self.first_pressed_time = 0


class ButtonControl:
    def __init__(self, buffer, dash, device='raspi'):
        self.buffer = buffer
        self.dash = dash
        self.device = device
        self.buttons = {}

        # 원래 CAN 메시지에 타이밍 맞춰 보내기 위해 사용하는 변수
        self.mirror_request = 0  # 0 중립, 1 접기 2 펴기
        self.fold_request_time = None
        self.door_open_request = 0
        self.door_open_start_time = 0

    def get_function(self, function_name):
        if function_name is None:
            return lambda *args, **kwargs: None
        if function_name == 'mirror_fold':
            return self.mirror_fold()
        if 'open_door' in function_name:
            return self.open_door(function_name[-2:])

    def add_button(self, btn_name):
        self.buttons[btn_name] = Button(btn_name)

    def assign(self, btn_name, press_type, function_name):
        self.buttons[btn_name].function[press_type] = self.get_function(function_name)

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x3e2):
            # Check Map Lamp Pressed
            map_lamp_left = self.buttons.get('MapLampLeft')
            map_lamp_right = self.buttons.get('MapLampRight')
            if map_lamp_left:
                if get_value(byte_data, 14, 1) == 1:
                    map_lamp_left.press()
                else:
                    map_lamp_left.release()
            if map_lamp_right:
                if get_value(byte_data, 15, 1) == 1:
                    map_lamp_right.press()
                else:
                    map_lamp_right.release()


        # Mirror Action
        if (bus == 0) and (address == 0x273):
            if self.mirror_request in [1, 2]:
                ret = modify_packet_value(byte_data, 24, 2, self.mirror_request)
                self.buffer.write_message_buffer(0, 0x273, ret)
                self.mirror_request = 0
                return ret

        # Door Open Action
        if (bus == 0) and (address == 0x1f9):
            if self.door_open_request == 0:
                pass
            else:
                cmd = {1: 'fl', 2: 'fr', 3: 'rl', 4: 'rr'}
                ret = command.get('door_open_' + cmd.get(self.door_open_request))
                if ret:
                    self.buffer.write_message_buffer(0, 0x1f9, ret)
                self.door_open_request = 0
                return ret
        return byte_data

    # Action 함수들
    def mirror_fold(self):
        if self.dash.mirror_folded[0] == 1 or self.dash.mirror_folded[1] == 1:
            self.mirror_request = 2
        else:
            self.mirror_request = 1

    def open_door(self, loc):
        if self.dash.parked == 1:
            indices = {'fl': 1, 'fr': 2, 'rl': 3, 'rr': 4}
            pos = indices.get(loc)
            if pos:
                self.door_open_request = pos



class Autopilot:
    def __init__(self, buffer, dash, sender=None, device='raspi', mars_mode=0, keep_wiper_speed=0, slow_wiper=0,
                 auto_distance=0):
        self.timer = 0
        self.buffer = buffer
        self.dash = dash
        self.tacc = 0
        self.autosteer = 0
        self.current_gear_position = 0
        self.last_gear_position = 0
        self.gear_down_pressed = 0
        self.gear_pressed_time = 0
        self.first_down_time = 0
        self.nag_disabled = 0
        self.mars_mode = mars_mode
        self.keep_wiper_speed = keep_wiper_speed
        self.slow_wiper = slow_wiper
        self.auto_distance = auto_distance
        self.manual_distance = 0
        if sender is not None:
            self.sender = sender
            if device == 'panda':
                self.device = 'panda'
            elif device == 'raspi':
                self.device = 'raspi'
            else:
                self.device = None
                print('device error. panda and raspi allowed')
                raise
        self.user_changed_wiper_request = 0
        self.wiper_mode_rollback_request = 0
        self.wiper_last_state = 0
        self.distance_current = 2
        self.distance_target = 3
        self.distance_far_pressed = 0
        self.distance_near_pressed = 0
        self.speed_deque = deque([0, 0, 0])
        self.smooth_speed = 0
        self.reset_distance()

    def run(self):
        # Dynamic Following Distance 제어를 위해 평균 속도를 산출 및 제어 (최근 3초 평균 속도 기준으로 제어)
        self.speed_deque.popleft()
        self.speed_deque.append(self.dash.ui_speed)
        self.smooth_speed = sum(s for _, s in self.speed_deque) / 3
        if self.auto_distance and not self.manual_distance and self.autosteer:
            if self.smooth_speed <= 60:
                self.distance_target = 3
            elif self.smooth_speed <= 80:
                self.distance_target = 4
            elif self.smooth_speed <= 100:
                self.distance_target = 5
            else:
                self.distance_target = 6
            self.set_distance(self.distance_target)

        # Mars Mode from Spleck's github (https://github.com/spleck/panda)
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

    def volume_updown(self):
        try:
            if self.device == 'panda':
                self.sender.can_send(0x3c2, command['volume_up'], 0)
                time.sleep(0.5)
                self.sender.can_send(0x3c2, command['volume_down'], 0)
                time.sleep(0.5)
            elif self.device == 'raspi':
                tx_frame = can.Message()
                tx_frame.channel = 'can0'
                tx_frame.dlc = 8
                tx_frame.arbitration_id = 0x3c2
                tx_frame.is_extended_id = False
                tx_frame.data = bytearray(command['volume_down'])
                self.sender.send(tx_frame)
                time.sleep(0.5)
                tx_frame.data = bytearray(command['volume_up'])
                self.sender.send(tx_frame)
                time.sleep(0.5)
            else:
                pass
        except Exception as e:
            print('Error occurred while control volumne up/down', e)

    def reset_distance(self):
        try:
            if self.device == 'panda':
                for i in range(6):
                    self.sender.can_send(0x3c2, command['distance_near'], 0)
                    time.sleep(0.05)
            elif self.device == 'raspi':
                tx_frame = can.Message()
                tx_frame.channel = 'can0'
                tx_frame.dlc = 8
                tx_frame.arbitration_id = 0x3c2
                tx_frame.is_extended_id = False
                for i in range(6):
                    tx_frame.data = bytearray(command['distance_near'])
                    self.sender.send(tx_frame)
                    time.sleep(0.25)
            else:
                pass
            print('Following distance set to closest')

        except Exception as e:
            print('Failed to set distance\n', e)

    def set_distance(self, target=None):
        if target:
            distance_target = target
        else:
            distance_target = self.distance_target
        print('distance target', distance_target, 'distance now', self.distance_current)
        gap = distance_target - self.distance_current
        if gap == 0:
            return
        else:
            print(f'Change Following distance from {self.distance_current} to {distance_target}')
            tx_frame = can.Message()
            tx_frame.channel = 'can0'
            tx_frame.dlc = 8
            tx_frame.arbitration_id = 0x3c2
            tx_frame.is_extended_id = False
            click_cnt = abs(gap)
            if gap > 0:
                cmd = command['distance_far']
                tx_frame.data = bytearray(cmd)
            else:
                cmd = command['distance_near']
                tx_frame.data = bytearray(cmd)
            for i in range(click_cnt):
                if self.device == 'panda':
                    self.sender.can_send(0x3c2, cmd, 0)
                elif self.device == 'raspi':
                    self.sender.send(tx_frame)
                time.sleep(0.25)
            self.distance_current = distance_target

    def disengage_autopilot(self):
        print('Autopilot Disengaged')
        self.tacc = 0
        self.autosteer = 0
        self.dash.tacc = 0
        self.dash.autopilot = 0
        self.first_down_time = 0
        self.gear_down_pressed = 0
        self.nag_disabled = 0
        self.dash.nag_disabled = 0
        print(f'current distance : {self.distance_current}, current target : {self.distance_target}')

    def engage_autopilot(self):
        self.gear_down_pressed = 0
        self.tacc = 0
        self.dash.tacc = 0
        self.autosteer = 1
        self.dash.autopilot = 1
        self.first_down_time = 0
        self.timer = 0
        if self.manual_distance == 1:
            self.set_distance(self.distance_target)
            self.manual_distance = 0

    def engage_tacc(self):
        self.gear_down_pressed = 1
        self.tacc = 1
        self.dash.tacc = 1
        self.autosteer = 0
        self.dash.autopilot = 0
        self.first_down_time = self.gear_pressed_time
        self.user_changed_wiper_request = 0
        self.wiper_mode_rollback_request = 0

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x39d):
            if (self.autosteer == 1) or (self.tacc == 1):
                brake_switch = get_value(byte_data, 16, 2)
                if brake_switch == 2:
                    self.disengage_autopilot()

        if (bus == 0) and (address == 0x273):
            if (self.keep_wiper_speed == 1) and (self.wiper_last_state != self.dash.wiper_state):
                # 와이퍼 상태가 바뀌었을 때
                if self.tacc or self.autosteer:
                    if self.dash.wiper_state == 2:
                        if self.user_changed_wiper_request == 1:
                            # 사용자가 Auto가 아닌 상태를 쓰다가 Auto로 바꾼 경우 롤백 없이 Auto를 계속 사용
                            self.wiper_mode_rollback_request = 0
                            self.wiper_last_state = self.dash.wiper_state
                        else:
                            # 오토파일럿 진입 직후 상태가 자동으로 Auto로 바뀌었다면, 마지막 설정으로 롤백 명령 시작
                            self.wiper_mode_rollback_request = 1
                    else:
                        # 사용자에 의해 바뀐 것
                        self.user_changed_wiper_request = 1
                        self.wiper_last_state = self.dash.wiper_state
                else:
                    if self.wiper_mode_rollback_request == 1:
                        # 오토파일럿 중 롤백 명령을 받은 상태가 유지되어 넘어온 것이니 마지막 설정을 유지하고 있다가, 오토가 아닌 값이 되면 롤백 해제
                        if self.dash.wiper_state != 2:
                            self.wiper_mode_rollback_request = 0
                            self.wiper_last_state = self.dash.wiper_state
                    else:
                        self.wiper_last_state = self.dash.wiper_state

            if (self.slow_wiper == 1) and self.dash.ui_speed <= 3:
                if self.dash.wiper_state in [0, 1, 2, 3, 4]:
                    target_state = 1
                elif self.dash.wiper_state in [5, 6]:
                    target_state = 3
                else:
                    target_state = self.dash.wiper_state
            else:
                if self.wiper_mode_rollback_request == 1:
                    target_state = self.wiper_last_state
                else:
                    target_state = self.dash.wiper_state

            if target_state != self.dash.wiper_state:
                ret = modify_packet_value(byte_data, 56, 3, target_state)
                self.buffer.write_message_buffer(0, 0x273, ret)
                return ret

        if (bus == 0) and (address == 0x229) and (self.dash.gear == 4):
            # 기어 스토크 상태 체크
            self.gear_pressed_time = time.time()
            self.current_gear_position = get_value(byte_data, 12, 3)
            if self.current_gear_position in [1, 2]:
                self.disengage_autopilot()
            elif self.current_gear_position in [3, 4]:
                if self.autosteer == 0 and self.last_gear_position == 0:
                    if self.gear_down_pressed == 0:
                        self.engage_tacc()
                    elif self.gear_down_pressed == 1:
                        gear_press_gap = (self.gear_pressed_time - self.first_down_time)
                        if gear_press_gap < 1:
                            print('Autopilot Engaged')
                            self.engage_autopilot()
                        else:
                            self.first_down_time = self.gear_pressed_time
                if (self.mars_mode == 1) and (self.current_gear_position == 4) and (self.autosteer == 1) and (
                        self.nag_disabled == 0):
                    self.nag_disabled = 1
                    self.dash.nag_disabled = 1
                    print('NAG Eliminator Activated')
                    self.volume_updown()
            elif self.current_gear_position == 0:
                if (self.autosteer == 0) and (self.first_down_time != 0) and (
                        time.time() - self.gear_pressed_time) >= 1:
                    self.first_down_time = 0
                    self.gear_down_pressed = 0
            self.last_gear_position = self.current_gear_position

        if (bus == 0) and (address == 0x3c2):
            mux = get_value(byte_data, 0, 2)
            if mux == 1:
                far_state = get_value(byte_data, 8, 2)
                near_state = get_value(byte_data, 10, 2)
                if far_state == 2:
                    self.distance_far_pressed = 1
                else:
                    if self.distance_far_pressed == 1:
                        if self.distance_current < 7:
                            self.distance_current += 1
                            print(f'Following distance set to {self.distance_current}')
                    self.distance_far_pressed = 0
                if near_state == 2:
                    self.distance_near_pressed = 1
                else:
                    if self.distance_near_pressed == 1:
                        if self.distance_current > 2:
                            self.distance_current -= 1
                            print(f'Following distance set to {self.distance_current}')
                    self.distance_near_pressed = 0

                # 수동으로 조작한 거리 단계는 타겟으로 인정. 다음 오토파일럿을 걸 때 목표로 자동 세팅
                if self.tacc or self.autosteer:
                    self.distance_target = self.distance_current
                    self.manual_distance = 1

        return byte_data


class RearCenterBuckle:
    def __init__(self, buffer, mode=0):
        self.buffer = buffer
        self.mode = mode
        # mode: 0/None - 비활성화, 1 - 뒷좌석 중앙만, 2 - 모두

    def check(self, bus, address, byte_data):
        if not self.mode:
            return False
        mux = get_value(byte_data, loc=0, length=2, endian='little', signed=False)
        if mux == 0:
            if self.mode == 1:
                # 뒷좌석 가운데자리 착좌센서 끄고, 안전벨트 스위치 켜기
                ret = modify_packet_value(byte_data, 54, 2, 1)
                ret = modify_packet_value(ret, 62, 2, 2)
                self.buffer.write_message_buffer(bus, address, ret)
            elif self.mode == 2:
                # ★★★★ Warning : 뒷좌석 안전벨트 미착용 상태로 승객을 태우는 것은 매우 위험하며, 도로교통법 위반입니다. ★★★★★
                # 짐을 쌓은 상태로 부득이 정리가 어려운 경우에만 사용하세요.
                ret = modify_packet_value(byte_data, 54, 2, 1)
                ret = modify_packet_value(ret, 62, 2, 2)
                # Disable rearLeftOccupancySwitch
                ret = modify_packet_value(ret, 56, 2, 1)
                # Disable rearRightOccupancySwitch
                ret = modify_packet_value(ret, 58, 2, 1)
                self.buffer.write_message_buffer(bus, address, ret)
            return ret
        return byte_data


class FreshAir:
    def __init__(self, buffer, dash, enabled=0):
        self.buffer = buffer
        self.dash = dash
        self.enabled = enabled
        self.recirc_mode = 1
        # 마지막으로 Frseh로 바뀐 시간, 마지막으로 Recirc로 바뀐 시간
        self.last_mode_change = time.time()
        # n명 탑승 시 (a분 내기, b분 외기)
        self.time_dict = {0: (10, 5),
                          1: (10, 5),
                          2: (7, 8),
                          3: (5, 10),
                          4: (0, 1440),
                          5: (0, 1440)}

    def check(self, bus, address, byte_data):
        if not self.enabled:
            return byte_data
        if (bus == 0) and (address == 0x2f3):
            if self.dash.recirc_mode == 0:
                parameters = self.time_dict.get(self.dash.passenger_cnt)
                if parameters:
                    recirc_time, fresh_time = parameters
                else:
                    return byte_data
                now = time.time()
                elapsed = (now - self.last_mode_change)
                if (self.recirc_mode == 1) and (elapsed > (60 * recirc_time)):
                    # 내기 모드로 지정 시간을 넘었을 때
                    self.recirc_mode = 2
                    self.last_mode_change = now
                elif (self.recirc_mode == 2) and (elapsed > (60 * fresh_time)):
                    # 외기 모드로 지정 시간을 넘었을 때
                    self.recirc_mode = 1
                    self.last_mode_change = now
                ret = modify_packet_value(byte_data, 20, 2, self.recirc_mode)
                self.buffer.write_message_buffer(bus, address, ret)
                return ret
        return byte_data


class KickDown:
    def __init__(self, buffer, dash, enabled=0):
        self.buffer = buffer
        self.dash = dash
        self.enabled = enabled
        self.apply = 0

    def check(self, bus, address, byte_data):
        if not self.enabled:
            return byte_data
        if (bus == 0) and (address == 0x39d):
            if self.apply:
                brake_switch = get_value(byte_data, 16, 2)
                if brake_switch == 2:
                    print('Brake Pressed, Kick Down mode disabled')
                    self.apply = 0

        if (bus == 0) and (address == 0x334):
            if (self.dash.drive_mode == 0) and (self.dash.accel_pedal_pos > 90) and (not self.apply):
                print('------- Kick Down / Sports Mode On -------')
                self.apply = 1
            if self.apply:
                ret = make_new_packet(0x334, byte_data, [(5, 2, 1)])
                self.buffer.write_message_buffer(bus, address, ret)
                return ret

        return byte_data


class TurnSignal:
    def __init__(self, buffer, dash, enabled=0):
        # up = right = 4,  down = left = 8
        self.crc_right = (163, 208, 18, 235, 235, 187, 116, 102, 7, 102, 218, 16, 2, 43, 151, 246)
        self.crc_right_half = (135, 244, 54, 207, 207, 159, 80, 66, 35, 66, 254, 52, 38, 15, 179, 210)
        self.crc_left = (235, 152, 90, 163, 163, 243, 60, 46, 79, 46, 146, 88, 74, 99, 223, 190)
        self.crc_left_half = (191, 204, 14, 247, 247, 167, 104, 122, 27, 122, 198, 12, 30, 55, 139, 234)
        self.buffer = buffer
        self.dash = dash
        self.enabled = enabled
        self.turn_indicator = 0  # 8 = left, 4 = right, 6 = left half, 2 = right half
        self.right_dial_click_time = 0

    def check(self, bus, address, byte_data):
        if not self.enabled:
            return byte_data
        if (bus == 0) and (address == 0x249):
            if self.turn_indicator == 0:
                return byte_data
            else:
                counter = (get_value(byte_data, 8, 4) + 1) % (2 ** 4)
                if self.turn_indicator == 8:
                    crc = self.crc_left[counter]
                elif self.turn_indicator == 6:
                    crc = self.crc_left_half[counter]
                elif self.turn_indicator == 4:
                    crc = self.crc_right[counter]
                elif self.turn_indicator == 2:
                    crc = self.crc_right_half[counter]
                else:
                    crc = None
                if crc is not None:
                    ret = modify_packet_value(byte_data, 8, 4, counter)
                    ret = modify_packet_value(ret, 16, 4, self.turn_indicator)
                    ret = modify_packet_value(ret, 0, 8, crc)
                    self.buffer.write_message_buffer(bus, address, ret)
                return ret

        if (bus == 0) and (address == 0x3c2):
            if (self.dash.autopilot == 1) or (self.dash.tacc == 1):
                self.turn_indicator = 0
                return byte_data
            if get_value(byte_data, 0, 2) == 1:
                if get_value(byte_data, 8, 2) == 2:
                    self.right_dial_click_time = time.time()
                    self.turn_indicator = 6
                elif get_value(byte_data, 10, 2) == 2:
                    self.right_dial_click_time = time.time()
                    self.turn_indicator = 2
                else:
                    if self.turn_indicator != 0:
                        if time.time() - self.right_dial_click_time > 0.1:
                            self.turn_indicator = 0
        return byte_data
