import time
import threading

from packets import get_value, modify_packet_value


class Button:
    def __init__(self, manager, btn_name, short_time=0.5, long_time=1.0):
        self.dash = manager.dash
        self.buffer = manager.buffer
        self.name = btn_name
        self.is_pressed = False
        self.last_press_time = 0
        self.last_release_time = 0
        self.long_click_threshold = long_time  # 롱클릭 인식 시간 (1초)
        self.click_timeout = short_time  # 더블클릭 인식 시간 간격 (0.5초)
        self.long_click_timer = None
        self.single_click_timer = None
        self.args = None
        self.function = {
            'short': lambda *args, **kwargs: None,
            'long': lambda *args, **kwargs: None,
            'double': lambda *args, **kwargs: None,
            'short_park': lambda *args, **kwargs: None,
            'long_park': lambda *args, **kwargs: None,
            'double_park': lambda *args, **kwargs: None,
            'short_drive': lambda *args, **kwargs: None,
            'long_drive': lambda *args, **kwargs: None,
            'double_drive': lambda *args, **kwargs: None
        }
        self.function_name = {
            'short': 'Undefined',
            'long': 'Undefined',
            'double': 'Undefined',
            'short_park': 'Undefined',
            'long_park': 'Undefined',
            'double_park': 'Undefined',
            'short_drive': 'Undefined',
            'long_drive': 'Undefined',
            'double_drive': 'Undefined'
        }
        self.click_count = 0
        self.lock = threading.Lock()  # 스레드 안전성을 위한 락

    def press(self, args=None):
        with self.lock:
            if args:
                self.args = args
            current_time = time.time()
            if not self.is_pressed:
                self.is_pressed = True
                self.last_press_time = current_time

                if self.click_count == 1:
                    time_since_last_release = current_time - self.last_release_time
                    if time_since_last_release <= self.click_timeout:
                        # 더블클릭 진행 중
                        self.click_count += 1
                        # 싱글클릭 타이머 취소
                        if self.single_click_timer:
                            self.single_click_timer.cancel()
                            self.single_click_timer = None
                        # 더블클릭 인식
                        self.on_click('double')
                        # 롱클릭 타이머 시작하지 않음
                        self.long_click_timer = None
                    else:
                        # 새로운 클릭으로 간주
                        self.click_count = 1
                        self.start_long_click_timer()
                else:
                    # 첫 번째 클릭
                    self.click_count = 1
                    self.start_long_click_timer()
            # 이미 눌려있는 상태에서는 추가 처리 없음

    def release(self):
        with self.lock:
            current_time = time.time()
            if self.is_pressed:
                self.is_pressed = False

                if self.long_click_timer:
                    self.long_click_timer.cancel()
                    self.long_click_timer = None

                if self.click_count == 2:
                    # 더블클릭 진행 중이었음
                    self.click_count = 0
                    # 더블클릭은 이미 인식되었으므로 추가 처리 없음
                elif self.click_count == 1:
                    # 싱글클릭 대기 타이머 시작
                    self.last_release_time = current_time
                    self.single_click_timer = threading.Timer(self.click_timeout, self.handle_single_click)
                    self.single_click_timer.start()

    def start_long_click_timer(self):
        # 롱클릭 타이머 시작
        self.long_click_timer = threading.Timer(self.long_click_threshold, self.handle_long_click)
        self.long_click_timer.start()

    def handle_long_click(self):
        with self.lock:
            if self.is_pressed and self.click_count == 1:
                # 롱클릭 인식
                self.on_click('long')
                # 상태 초기화
                self.click_count = 0
                if self.single_click_timer:
                    self.single_click_timer.cancel()
                    self.single_click_timer = None

    def handle_single_click(self):
        with self.lock:
            if self.click_count == 1:
                # 싱글클릭 인식
                self.on_click('short')
            self.click_count = 0

    def on_click(self, click_type):
        if click_type in ['short', 'long', 'double']:
            if self.dash.di.gear in [1, 3]:
                drive_state = click_type + '_park'
            elif self.dash.di.gear in [2, 4]:
                drive_state = click_type + '_drive'
            else:
                drive_state = click_type  # 기어 정보가 없을 때 기본 상태
            self.action(drive_state)
            self.action(click_type)

    def action(self, period):
        if self.function_name[period] != 'Undefined':
            print(f"{self.name} - {period} 액션 실행: {self.function_name[period]}")
        if self.args:
            if isinstance(self.args, (list, tuple)):
                self.function[period](*self.args)
            else:
                self.function[period](self.args)
        else:
            self.function[period]()
        self.args = None


class ButtonManager:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash
        self.buttons = {}

        # 원래 CAN 메시지에 타이밍 맞춰 보내기 위해 사용하는 변수
        self.mirror_request = 0  # 0 중립, 1 접기 2 펴기
        self.fold_request_time = None
        self.door_open_request = None
        self.door_open_start_time = 0

    def get_function(self, function_name):
        if function_name is None:
            return lambda *args, **kwargs: None
        if function_name == 'mirror_fold':
            return self.mirror_fold
        if 'open_door' in function_name:
            return lambda: self.open_door(function_name[-2:])
        if function_name == 'buckle_emulator':
            return self.buckle_emulator
        if function_name == 'mars_mode_toggle':
            return self.mars_mode_toggle
        return lambda *args, **kwargs: None

    def add_button(self, btn_name, short_time=0.5, long_time=1.0):
        self.buttons[btn_name] = Button(self, btn_name, short_time, long_time)

    def is_button(self, btn_name):
        if self.buttons.get(btn_name):
            return True
        else:
            return False

    def assign(self, btn_name, press_type, function_name):
        print(f'{btn_name} 버튼을 {press_type} 할 때 {function_name}에 연결')
        self.buttons[btn_name].function[press_type] = self.get_function(function_name)
        self.buttons[btn_name].function_name[press_type] = function_name

    def check(self, bus, address, byte_data):
        ret = byte_data
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

        if (bus == 0) and (address == 0x229):
            p_btn = self.buttons.get('ParkingButton')
            if p_btn:
                if get_value(byte_data, 16, 2) in [1, 2]:
                    p_btn.press()
                else:
                    p_btn.release()

        # Mirror Action
        if (bus == 0) and (address == 0x273):
            if self.mirror_request in [1, 2]:
                ret = modify_packet_value(byte_data, 24, 2, self.mirror_request)
                self.buffer.write_message_buffer(0, 0x273, ret)
                self.mirror_request = 0
                return ret

        # Door Open Action
        if (bus == 0) and (address == 0x1f9):
            if self.door_open_request is None:
                pass
            else:
                door_loc = str(self.door_open_request)
                if door_loc == 'fl':
                    ret = bytes.fromhex('6000000000000000')
                elif door_loc == 'fr':
                    ret = bytes.fromhex('0003000000000000')
                elif door_loc == 'rl':
                    ret = bytes.fromhex('0018000000000000')
                elif door_loc == 'rr':
                    ret = bytes.fromhex('00c0000000000000')
                if ret:
                    self.buffer.write_message_buffer(0, 0x1f9, ret)
                self.door_open_request = None
                return ret
        return byte_data

    # Action 함수들
    def mirror_fold(self):
        if self.dash.body.mirror_folded_left == 1 or self.dash.body.mirror_folded_right == 1:
            self.mirror_request = 2
        else:
            self.mirror_request = 1

    def open_door(self, loc):
        if self.dash.di.parked == 1:
            door_positions = ('fl', 'fr', 'rl', 'rr')
            if loc in door_positions:
                self.door_open_request = loc

    def buckle_emulator(self):
        self.dash.features.buckle_emulator ^= 1  # 0이면 1로, 1이면 0으로

    def mars_mode_toggle(self):
        self.dash.ap.mars_mode ^= 1
