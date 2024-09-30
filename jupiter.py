import os
import time
import can
import threading
from vcgencmd import Vcgencmd
from functions import initialize_canbus_connection, load_settings
from tesla import Buffer, Dashboard, Logger, Autopilot, RearCenterBuckle, ButtonManager, FreshAir, \
    KickDown, TurnSignal, Reboot, monitoring_addrs


class Jupiter(threading.Thread):
    def __init__(self, dash, settings):
        super().__init__()
        self.jupiter_online = True
        self.dash = dash
        self.vcgm = Vcgencmd()
        self.settings = settings

    def run(self):
        if not self.jupiter_online:
            return False
        # CAN Bus Device 초기화
        initialize_canbus_connection()
        can_bus = can.interface.Bus(channel='can0', interface='socketcan')
        bus_connected = 0
        bus_error = 0
        self.dash.bus_error_count = 0
        last_recv_time = time.time()
        bus = 0  # 라즈베리파이는 항상 0, panda는 다채널이므로 수신하면서 확인

        # 핵심 기능 로딩
        BUFFER = Buffer()
        LOGGER = Logger(BUFFER, self.dash, cloud=0, enabled=self.settings.get('Logger'))

        #  부가 기능 로딩
        AP = Autopilot(BUFFER, self.dash,
                       sender=can_bus,
                       device='raspi',
                       mars_mode=self.settings.get('MarsMode'),
                       keep_wiper_speed=self.settings.get('KeepWiperSpeed'),
                       slow_wiper=self.settings.get('SlowWiper'),
                       auto_distance=self.settings.get('AutoFollowingDistance'))

        BUCKLE = RearCenterBuckle(BUFFER, self.dash, mode=self.settings.get('RearCenterBuckle'))
        FRESH = FreshAir(BUFFER, self.dash, enabled=self.settings.get('AutoRecirculation'))
        KICKDOWN = KickDown(BUFFER, self.dash, enabled=self.settings.get('KickDown'))
        TURNSIGNAL = TurnSignal(BUFFER, self.dash, enabled=self.settings.get('AltTurnSignal'))
        REBOOT = Reboot(self.dash)
        BUTTON = ButtonManager(BUFFER, self.dash)
        BUTTON.add_button(btn_name='MapLampLeft')
        BUTTON.add_button(btn_name='MapLampRight')
        BUTTON.add_button(btn_name='ParkingButton', long_time=0.5)
        buttons_define = (
            ('MapLampLeft', 'short', self.settings.get('MapLampLeftShort')),
            ('MapLampLeft', 'long', self.settings.get('MapLampLeftLong')),
            ('MapLampLeft', 'double', self.settings.get('MapLampLeftDouble')),
            ('MapLampRight', 'short', self.settings.get('MapLampRightShort')),
            ('MapLampRight', 'long', self.settings.get('MapLampRightLong')),
            ('MapLampRight', 'double', self.settings.get('MapLampRightDouble')),
            ('ParkingButton', 'long', 'mirror_fold'),
        )
        for (btn, ptype, func) in buttons_define:
            if isinstance(func, str):
                functions = func.split(',')
                if len(functions) == 1:
                    BUTTON.assign(btn_name=btn, press_type=ptype, function_name=functions[0].strip())
                else:
                    BUTTON.assign(btn_name=btn, press_type=ptype + '_park', function_name=functions[0].strip())
                    BUTTON.assign(btn_name=btn, press_type=ptype + '_drive', function_name=functions[1].strip())

        while True:
            current_time = time.time()
            self.dash.current_time = current_time
            if (bus_connected == 1):
                if self.dash.bus_error_count > 5:
                    print('Bus Error Count Over, reboot')
                    os.system('sudo reboot')
                if bus_error == 1:
                    self.dash.bus_error_count += 1
                    print(f'Bus Error, {self.dash.bus_error_count}')
                    initialize_canbus_connection()
                    can_bus = can.interface.Bus(channel='can0', interface='socketcan')
                    bus_error = 0
                else:
                    if (current_time - last_recv_time >= 5):
                        print('bus error counted')
                        bus_error = 1
                        self.dash.bus_error_count += 1
                        last_recv_time = time.time()
            elif (bus_connected == 0) and (current_time - last_recv_time >= 10):
                print('Waiting until CAN Bus Connecting...',
                      time.strftime('%m/%d %H:%M:%S', time.localtime(last_recv_time)))
                initialize_canbus_connection()
                last_recv_time = time.time()

            ###################################################
            ############## 파트1. 메시지를 읽는 영역 ##############
            ###################################################
            try:
                recv_message = can_bus.recv(1)
            except Exception as e:
                print('메시지 수신 실패\n', e)
                bus_error = 1
                recv_message = None
                continue

            if recv_message is not None:
                last_recv_time = time.time()
                address = recv_message.arbitration_id
                signal = recv_message.data
                BUFFER.write_can_buffer(bus, address, signal)

                # 여러 로직에 활용하기 위한 차량 상태값 모니터링
                dash_item = monitoring_addrs.get(address)
                if dash_item is not None:
                    self.dash.update(dash_item, signal)
                self.dash.last_update = current_time

                ### 기어 상태 체크 / 로깅 시작 ###
                if address == 0x118 and (self.dash.clock is not None):
                    self.dash.update('DriveSystemStatus', signal)
                    if self.dash.gear == 4:
                        if self.dash.parked == 1:   # Park(1) → Drive(4)
                            print(f'Drive Gear Detected... Recording Drive history from {self.dash.clock}')
                            self.dash.parked = 0
                            self.dash.drive_time = 0
                            self.dash.drive_finished = 0
                            LOGGER.initialize()
                    elif self.dash.gear == 1:
                        if self.dash.parked == 0:  # Drive(4) → Park(1)
                            print('Parking Gear Detected... Saving Drive history')
                            self.dash.parked = 1
                            self.dash.drive_time = 0
                            self.dash.drive_finished = 1
                            LOGGER.close()
                        if self.settings.get('MirrorAutoFold'):
                            if self.dash.passenger_cnt == 0 and self.dash.drive_finished == 1:
                                BUTTON.mirror_request = 1
                                self.dash.drive_finished = 0
                    else:
                        pass

                # 1초에 한번 전송되는 차량 시각 정보 수신
                if address == 0x528:
                    TICK = True
                    bus_connected = 1
                    self.dash.update('UnixTime', signal)
                else:
                    TICK = False

                # 매 1초마다 실행할 액션 지정
                if TICK:
                    self.dash.device_temp = self.vcgm.measure_temp()
                    if self.dash.gear == 4:
                        self.dash.drive_time += 1
                    print(f'Clock: {self.dash.clock}  Temperature: {self.dash.device_temp}')

                    # for bid, val in self.dash.beacon.items():
                    #     print(f'{bid} value is now {val}')

                    ##### Log writer ######
                    if (LOGGER.file is not None):
                        LOGGER.write()

                    ##### Mars Mode ######
                    AP.tick()

                # 실시간 패킷 인식 및 변조
                if address == 0x1f9:
                    signal = BUTTON.check(bus, address, signal)
                if address == 0x229:
                    signal = BUTTON.check(bus, address, signal)
                if address == 0x249:
                    ##### 오토파일럿이 아닐 때 우측 다이얼을 이용해 깜빡이를 켜기 위함 - 스토크 동작 에뮬레이션 #####
                    signal = TURNSIGNAL.check(bus, address, signal)
                if address == 0x3e2:
                    ##### 맵등 버튼을 길게 눌러 기능을 제공하기 위해, 눌림 상태를 점검 #####
                    signal = BUTTON.check(bus, address, signal)
                if address == 0x273:
                    ##### 와이퍼 상태 유지 #####
                    signal = AP.check(bus, address, signal)
                    ##### 미러 폴딩 기능 동작 #####
                    signal = BUTTON.check(bus, address, signal)
                if address == 0x3c2:
                    ##### 주행 중 뒷좌석 가운데 안전벨트 체크 해제 #####
                    signal = BUCKLE.check(bus, address, signal)
                    ##### 오토파일럿이 아닐 때 우측 다이얼을 이용해 깜빡이를 켜기 위함 - 버튼 체크 #####
                    signal = TURNSIGNAL.check(bus, address, signal)
                    ##### 오토파일럿이 우측 다이얼 조작을 통한 거리 설정을 인지하게 하기 위함 #####
                    signal = AP.check(bus, address, signal)
                    ##### 재부팅 명령 모니터링 ###
                    signal = REBOOT.check(bus, address, signal)
                if address == 0x334:
                    ###### Kick Down 동작을 통해 페달맵을 Comfort → Sport로 변경 #####
                    signal = KICKDOWN.check(bus, address, signal)
                if address == 0x39d:
                    ##### 브레이크 밟힘 감지 - 브레이크를 감지해 해제해야 하는 기능 #####
                    signal = AP.check(bus, address, signal)
                    signal = KICKDOWN.check(bus, address, signal)
                if address == 0x229:
                    ##### 기어 스토크 조작 인식 - 오토파일럿 동작 여부 확인 #####
                    signal = AP.check(bus, address, signal)
                if address == 0x2f3:
                    ##### 실내 이산화탄소 농도 관리를 위해 내/외기 모드 자동 변경 (탑승인원 비례) #####
                    signal = FRESH.check(bus, address, signal)

            ###################################################
            ############ 파트2. 메시지를 보내는 영역 ##############
            ###################################################

            try:
                if self.dash.occupancy == 0:
                    BUFFER.flush_message_buffer()
                    continue
                else:
                    for _, address, signal in BUFFER.message_buffer:
                        can_bus.send(can.Message(arbitration_id=address,
                                                 channel='can0',
                                                 data=bytearray(signal),
                                                 dlc=len(bytearray(signal)),
                                                 is_extended_id=False))
            except Exception as e:
                print("메시지 발신 실패, Can Bus 리셋 시도 \n", e)
                bus_error = 1

            BUFFER.flush_message_buffer()

    def stop(self):
        self.jupiter_online = False


def main():
    settings = load_settings()
    DASH = Dashboard()
    J = Jupiter(DASH, settings)
    J.start()

    if settings.get('NavdyHud') == 1:
        from navdy import Hud
        H = Hud(DASH)
        H.start()

if __name__ == '__main__':
    main()
