import time
from collections import deque

from features.buttons import Button
from packets import get_value, modify_packet_value


class Autopilot:
    def __init__(self, buffer, dash, sender=None, device='raspi', mars_mode=0, keep_wiper_speed=0, slow_wiper=0,
                 auto_distance=0):
        self.timer = 0
        self.buffer = buffer
        self.dash = dash
        self.tacc = 0
        self.autosteer = 0
        self.autosteer_active_time = 0
        self.continuous_ap_active = 0
        self.continuous_ap_request = 0
        self.continuous_ap_request_time = 0
        self.turn_indicator_on = 0
        self.turn_indicator_off_time = 0
        self.disengage_time = 0
        self.current_gear_position = 0
        self.nag_disabled = 0
        self.mars_mode = mars_mode if mars_mode is not None else 0
        self.dash.ap.mars_mode = self.mars_mode
        self.keep_wiper_speed = keep_wiper_speed if keep_wiper_speed is not None else 0
        self.slow_wiper = slow_wiper if slow_wiper is not None else 0
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
        self.stalk_crc = [73, 75, 93, 98, 76, 78, 210, 246, 67, 170, 249, 131, 70, 32, 62, 52]
        self.stalk_down_count = 0
        self.stalk_down_time = 0
        self.stalk_up = Button(self, 'right_stalk_up')
        self.stalk_up.function['short_drive'] = self.disengage_autopilot
        self.stalk_up.function['long_drive'] = self.disengage_autopilot
        self.stalk_up.function['double_drive'] = self.disengage_autopilot
        self.stalk_up.function_name['short_drive'] = 'Disengage Autopilot'
        self.stalk_up.function_name['long_drive'] = 'Disengage Autopilot'
        self.stalk_up.function_name['double_drive'] = 'Disengage Autopilot'
        self.stalk_down = Button(self, 'right_stalk_down')
        self.stalk_down.function['short_drive'] = self.engage_tacc
        self.stalk_down.function_name['short_drive'] = 'TACC / NAG Eliminator'
        self.stalk_down.function['double_drive'] = self.engage_autopilot
        self.stalk_down.function_name['double_drive'] = 'Autopilot / Turn Signal on AP'
        self.stalk_down.function['long_drive'] = self.activate_turn_indicator_on
        self.switch_commands = []
        self.last_switch_command_time = 0
        self.reset_distance()

    def tick(self):
        # Dynamic Following Distance 제어를 위해 평균 속도를 산출 및 제어 (최근 3초 평균 속도 기준으로 제어)
        self.mars_mode = self.dash.ap.mars_mode
        self.timer += 1
        self.speed_deque.popleft()
        self.speed_deque.append(self.dash.di.speed)
        self.smooth_speed = sum(s for s in self.speed_deque) / 3
        if self.auto_distance and (not self.manual_distance) and (self.autosteer or self.tacc):
            if self.smooth_speed <= 20:
                self.distance_target = 3
            elif self.smooth_speed <= 60:
                self.distance_target = 2
            elif self.smooth_speed <= 80:
                self.distance_target = 3
            elif self.smooth_speed <= 100:
                self.distance_target = 4
            else:
                self.distance_target = 5
            if self.distance_target != self.distance_current:
                self.set_distance(self.distance_target)
                self.timer = 0

        # Mars Mode from Spleck's github (https://github.com/spleck/panda)
        # 운전 중 스티어링 휠을 잡고 정확히 조향하는 것은 운전자의 의무입니다.
        # 미국 생산 차량에서만 다이얼을 이용한 NAG 제거가 유효하며, 중국 생산차량은 적용되지 않습니다.
        if self.mars_mode and self.autosteer == 1 and self.nag_disabled == 1:
            if self.timer == 5:
                print('Right Scroll Wheel Down')
                self.switch_commands.append('speed_down')
            elif self.timer == 6:
                print('Right Scroll Wheel Up')
                self.switch_commands.append('speed_up')
        if self.timer >= 7:
            self.timer = 0

    def reset_distance(self):
        for i in range(6):
            self.switch_commands.append('distance_near')

    def set_distance(self, target=None):
        if target:
            distance_target = target
        else:
            distance_target = self.distance_target
        if distance_target != self.distance_current:
            print('distance target', distance_target, 'distance now', self.distance_current)
        gap = distance_target - self.distance_current
        if gap == 0:
            return
        else:
            print(f'Change Following distance from {self.distance_current} to {distance_target}')
            if gap > 0:
                cmd = 'distance_far'
                self.distance_current += 1
            else:
                cmd = 'distance_near'
                self.distance_current -= 1
            self.switch_commands.append(cmd)

    def disengage_autopilot(self, depth=None):
        if depth == 1:
            if self.continuous_ap_active == 1:
                if self.autosteer:
                    # 해제된 시점으로부터 2초 내에 방향지시등이 켜지면 Continuous AP 동작하기 위해 시간을 기록
                    self.disengage_time = time.time()
                    if self.turn_indicator_on:
                        # 오토파일럿 중 방향지시등이 먼저 켜진 상태에서 스토크를 약하게 올려 해제했을 때
                        print('Continuous Autopilot Requested')
                        self.continuous_ap_request = 1
                else:
                    self.disengage_time = 0
            else:
                self.disengage_time = 0
                self.nag_disabled = 0
                self.dash.ap.nag_disabled = 0
        elif depth == 2:
            self.disengage_time = 0
            self.continuous_ap_active = 0
            self.continuous_ap_request = 0
            self.nag_disabled = 0
            self.dash.ap.nag_disabled = 0
            if self.dash.di.gear == 4:
                if self.continuous_ap_active:
                    print('Continuous Autopilot Deactivated')
        if self.autosteer or self.tacc:
            print('Autopilot Disengaged')
            print(f'current distance : {self.distance_current}, current target : {self.distance_target}')
        self.tacc = 0
        self.autosteer = 0
        self.dash.ap.tacc = 0
        self.dash.ap.autopilot = 0
        self.dash.ap.turn_signal_on_ap = 0
        self.autosteer_active_time = 0

    def engage_autopilot(self, depth=None):
        if self.autosteer == 0:
            print('Autopilot Engaged')
            self.tacc = 0
            self.dash.ap.tacc = 0
            self.autosteer = 1
            self.dash.ap.autopilot = 1
            self.autosteer_active_time = time.time()
            self.user_changed_wiper_request = 0
            self.wiper_mode_rollback_request = 0
            self.timer = 0
            self.manual_distance = 0
            self.nag_disabler()

    def engage_tacc(self, depth=None):
        if self.tacc == 0 and self.autosteer == 0:
            self.tacc = 1
            self.dash.ap.tacc = 1
            self.user_changed_wiper_request = 0
            self.wiper_mode_rollback_request = 0
            self.manual_distance = 0
        else:
            if depth == 4:
                self.activate_continuous_ap()

    def nag_disabler(self):
        if self.mars_mode:
            self.nag_disabled = 1
            self.dash.ap.nag_disabled = 1
            print('NAG Eliminator Activated')

    def activate_continuous_ap(self, depth=None):
        if self.autosteer:
            if (self.autosteer_active_time != 0) and (time.time() - self.autosteer_active_time > 0.5):
                self.continuous_ap_active = 1
                print('Continuous Autopilot Activated')

    def activate_turn_indicator_on(self, depth=None):
        if (self.autosteer or self.tacc) and self.dash.features.alt_turn_signal:
            self.dash.ap.turn_signal_on_ap = 1
            print('ALT Turn indicator on AP activated')

    def right_stalk_double_down(self):
        print('Continuous Autopilot Stalk Action Requested')
        self.stalk_down_count = 2

    def dial_work(self, byte_data):
        ret = byte_data
        # 동시에 두가지 다이얼 조작이 충돌하지 않게 하기 위한 처리
        if self.switch_commands:
            if time.time() - self.last_switch_command_time >= 0.2:
                command_name = self.switch_commands[0]
                self.last_switch_command_time = time.time()
            else:
                command_name = ''
            # Left dial 충돌 회피
            if 'volume' in command_name:
                swcLeftDoublePress = get_value(ret, 41, 1)
                swcLeftPressed = get_value(ret, 5, 2)
                swcLeftScrollTicks = get_value(ret, 16, 6, signed=True)
                swcLeftTiltLeft = get_value(ret, 14, 2)
                swcLeftTiltRight = get_value(ret, 3, 2)
                if swcLeftDoublePress == 0 and swcLeftScrollTicks == 0 and \
                        swcLeftPressed == 1 and swcLeftTiltLeft == 1 and swcLeftTiltRight == 1:
                    cmd = self.switch_commands.pop(0)
                    if cmd == 'volume_down':  # down value 1, up value -1
                        ret = modify_packet_value(ret, 16, 6, 1, signed=True)
                    elif cmd == 'volume_up':
                        ret = modify_packet_value(ret, 16, 6, -1, signed=True)
                    else:
                        pass
                    self.buffer.write_message_buffer(0, 0x3c2, ret)
            elif ('speed' in command_name) or ('distance' in command_name):
                swcRightDoublePress = get_value(ret, 42, 1)
                swcRightPressed = get_value(ret, 12, 2)
                swcRightScrollTicks = get_value(ret, 24, 6, signed=True)
                swcRightTiltLeft = get_value(ret, 8, 2)
                swcRightTiltRight = get_value(ret, 10, 2)
                if swcRightDoublePress == 0 and swcRightScrollTicks == 0 and \
                        swcRightPressed == 1 and swcRightTiltLeft == 1 and swcRightTiltRight == 1:
                    cmd = self.switch_commands.pop(0)
                    if cmd == 'speed_down':
                        ret = modify_packet_value(ret, 24, 6, -1, signed=True)
                    elif cmd == 'speed_up':
                        ret = modify_packet_value(ret, 24, 6, 1, signed=True)
                    elif cmd == 'distance_far':
                        ret = modify_packet_value(ret, 8, 2, 2)
                    elif cmd == 'distance_near':
                        ret = modify_packet_value(ret, 10, 2, 2)
                    else:
                        pass
                    self.buffer.write_message_buffer(0, 0x3c2, ret)
            else:
                pass
            return ret
        else:
            return ret

    def check(self, bus, address, byte_data):
        ret = byte_data
        # continuous ap 판단
        if self.continuous_ap_request == 1:
            if self.turn_indicator_on == 0 and time.time() - self.turn_indicator_off_time > 2:
                if self.dash.di.speed >= 30 and self.dash.di.accel_pedal_pos > 0:
                    self.right_stalk_double_down()
                self.continuous_ap_request = 0
                self.turn_indicator_off_time = 0

        if self.dash.di.gear != 4:
            self.disengage_autopilot(depth=2)

        if (bus == 0) and (address == 0x39d):
            if self.dash.ibst.driver_brake == 2:
                self.disengage_autopilot(depth=2)

        if (bus == 0) and (address == 0x273):
            if (self.keep_wiper_speed == 1) and (self.wiper_last_state != self.dash.ui_controls.wiper_state):
                # 와이퍼 상태가 바뀌었을 때
                if self.tacc or self.autosteer:
                    if self.dash.ui_controls.wiper_state == 2:
                        if self.user_changed_wiper_request == 1:
                            # 사용자가 Auto가 아닌 상태를 쓰다가 Auto로 바꾼 경우 롤백 없이 Auto를 계속 사용
                            self.wiper_mode_rollback_request = 0
                            self.wiper_last_state = self.dash.ui_controls.wiper_state
                        else:
                            # 오토파일럿 진입 직후 상태가 자동으로 Auto로 바뀌었다면, 마지막 설정으로 롤백 명령 시작
                            self.wiper_mode_rollback_request = 1
                    else:
                        # 사용자에 의해 바뀐 것
                        self.user_changed_wiper_request = 1
                        self.wiper_last_state = self.dash.ui_controls.wiper_state
                else:
                    if self.wiper_mode_rollback_request == 1:
                        # 오토파일럿 중 롤백 명령을 받은 상태가 유지되어 넘어온 것이니 마지막 설정을 유지하고 있다가, 오토가 아닌 값이 되면 롤백 해제
                        if self.dash.ui_controls.wiper_state != 2:
                            self.wiper_mode_rollback_request = 0
                            self.wiper_last_state = self.dash.ui_controls.wiper_state
                    else:
                        self.wiper_last_state = self.dash.ui_controls.wiper_state

            if (self.slow_wiper == 1) and self.dash.di.speed <= 3:
                if self.dash.ui_controls.wiper_state in [0, 1, 2, 3, 4]:
                    target_state = 1
                elif self.dash.ui_controls.wiper_state in [5, 6]:
                    target_state = 3
                else:
                    target_state = self.dash.ui_controls.wiper_state
            else:
                if self.wiper_mode_rollback_request == 1:
                    target_state = self.wiper_last_state
                else:
                    target_state = self.dash.ui_controls.wiper_state

            if target_state != self.dash.ui_controls.wiper_state:
                ret = modify_packet_value(byte_data, 56, 3, target_state)
                self.buffer.write_message_buffer(0, 0x273, ret)

        if (bus == 0) and (address == 0x229) and (self.dash.di.gear == 4) and (self.dash.di.drive_time > 1):
            # Continuous Autopilot을 위한 방향지시등 상태 업데이트
            if self.dash.body.turn_indicator_left or self.dash.body.turn_indicator_right:
                self.turn_indicator_on = 1
                if self.disengage_time != 0:
                    # 오토스티어 해제가 먼저 되었고, 방향지시등이 나중에 점등 된 경우. 오토스티어 해제 2초 이내라면
                    if time.time() - self.disengage_time <= 2:
                        self.continuous_ap_request = 1
                    self.disengage_time = 0
            else:
                if self.turn_indicator_on:
                    self.turn_indicator_off_time = time.time()
                    self.turn_indicator_on = 0

            # 기어 스토크 상태 체크
            self.current_gear_position = get_value(byte_data, 12, 3)
            if self.current_gear_position in [1, 2]:
                self.stalk_up.press(self.current_gear_position)
                self.stalk_down.release()
            elif self.current_gear_position in [3, 4]:
                self.stalk_down.press(self.current_gear_position)
                self.stalk_up.release()
            elif self.current_gear_position == 0:
                self.stalk_up.release()
                self.stalk_down.release()

            if self.stalk_down_count == 2 or (self.stalk_down_time != 0 and time.time() - self.stalk_down_time >= 0.5):
                counter = (get_value(byte_data, 8, 4) + 1) % (2 ** 4)
                crc = self.stalk_crc[counter]
                ret = modify_packet_value(byte_data, 8, 4, counter)
                ret = modify_packet_value(ret, 12, 3, 3)  # half down
                ret = modify_packet_value(ret, 0, 8, crc)
                self.buffer.write_message_buffer(bus, address, ret)
                self.stalk_down_count -= 1
                if self.stalk_down_count == 1:
                    self.stalk_down_time = time.time()
                elif self.stalk_down_count == 0:
                    self.stalk_down_time = 0
                    self.engage_autopilot(depth=2)

        if (bus == 0) and (address == 0x3c2):
            mux = get_value(byte_data, 0, 2)
            if mux == 1:
                # 다이얼 명령어 처리
                ret = self.dial_work(byte_data)
                # 현재 상태 읽기
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
                if (far_state == 2 or near_state == 2) and (self.tacc or self.autosteer):
                    self.distance_target = self.distance_current
                    if self.dash.ap.turn_signal_on_ap:
                        self.manual_distance = 0
                    else:
                        self.manual_distance = 1
        return ret
