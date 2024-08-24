import os
import time
import can
import threading
import asyncio
from functions import initialize_canbus_connection, load_settings
from tesla import Buffer, Dashboard, Logger, Autopilot, RearCenterBuckle, MapLampControl, FreshAir, \
    KickDown, TurnSignal, monitoring_addrs


class Jupiter(threading.Thread):
    def __init__(self, dash):
        super().__init__()
        self.jupiter_online = True
        self.dash = dash
        from vcgencmd import Vcgencmd
        self.vcgm = Vcgencmd()

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
        settings = load_settings()
        BUFFER = Buffer()
        LOGGER = Logger(BUFFER, self.dash, cloud=0, enabled=settings.get('Logger'))

        #  부가 기능 로딩
        AP = Autopilot(BUFFER, self.dash,
                       sender=can_bus,
                       device='raspi',
                       mars_mode=settings.get('MarsMode'),
                       keep_wiper_speed=settings.get('KeepWiperSpeed'),
                       slow_wiper=settings.get('SlowWiper'),
                       auto_distance=settings.get('AutoFollowingDistance'))

        BUCKLE = RearCenterBuckle(BUFFER, mode=settings.get('RearCenterBuckle'))
        MAPLAMP = MapLampControl(BUFFER, self.dash, device='raspi',
                                 left=settings.get('MapLampLeft'),
                                 right=settings.get('MapLampRight'))
        FRESH = FreshAir(BUFFER, self.dash, enabled=settings.get('AutoRecirculation'))
        KICKDOWN = KickDown(BUFFER, self.dash, enabled=settings.get('KickDown'))
        TURNSIGNAL = TurnSignal(BUFFER, self.dash, enabled=settings.get('AltTurnSignal'))
        TICK = False  # 차에서 1초 간격 Unix Time을 보내주는 타이밍인지 여부

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
                    try:
                        AP.sender = can_bus
                        if self.dash.occupancy == 1:
                            AP.volume_updown()
                    except:
                        pass
                    bus_error = 0
                else:
                    if (current_time - last_recv_time >= 5):
                        print('bus error counted')
                        self.dash.bus_error_count += 1
                        last_recv_time = time.time()
            elif (bus_connected == 0) and (current_time - last_recv_time >= 5):
                print('Waiting until CAN Bus Connecting...',
                      time.strftime('%m/%d %H:%M:%S', time.localtime(last_recv_time)))
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
                    if (self.dash.gear == 4) and (self.dash.parked):  # Drive
                        print(f'Drive Gear Detected... Recording Drive history from {self.dash.clock}')
                        self.dash.parked = 0
                        self.dash.drive_start_time = current_time
                        LOGGER.initialize()
                    elif (self.dash.gear == 1) and (not self.dash.parked):  # Park
                        print('Parking Gear Detected... Saving Drive history')
                        self.dash.parked = 1
                        self.dash.drive_start_time = 0
                        LOGGER.close()
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
                    print(f'Clock: {self.dash.clock}  Temperature: {self.dash.device_temp}')

                    ##### Log writer ######
                    if (LOGGER.file is not None):
                        LOGGER.write()

                    ##### Mars Mode ######
                    AP.run()

                # 실시간 패킷 인식 및 변조
                if address == 0x1f9:
                    signal = MAPLAMP.check(bus, address, signal)
                if address == 0x249:
                    ##### 오토파일럿이 아닐 때 우측 다이얼을 이용해 깜빡이를 켜기 위함 - 스토크 동작 에뮬레이션 #####
                    signal = TURNSIGNAL.check(bus, address, signal)
                if address == 0x3e2:
                    ##### 맵등 버튼을 길게 눌러 기능을 제공하기 위해, 눌림 상태를 점검 #####
                    signal = MAPLAMP.check(bus, address, signal)
                if address == 0x273:
                    ##### 와이퍼 상태 유지 #####
                    signal = AP.check(bus, address, signal)
                    ##### 미러 폴딩 기능 동작 #####
                    signal = MAPLAMP.check(bus, address, signal)
                if address == 0x3c2:
                    ##### 주행 중 뒷좌석 가운데 안전벨트 체크 해제 #####
                    signal = BUCKLE.check(bus, address, signal)
                    ##### 오토파일럿이 아닐 때 우측 다이얼을 이용해 깜빡이를 켜기 위함 - 버튼 체크 #####
                    signal = TURNSIGNAL.check(bus, address, signal)
                    ##### 오토파일럿이 우측 다이얼 조작을 통한 거리 설정을 인지하게 하기 위함 #####
                    signal = AP.check(bus, address, signal)
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
    DASH = Dashboard()
    J = Jupiter(DASH)
    J.start()

    from navdy import Hud, HudConnector
    HC = HudConnector()
    H = Hud(HC, DASH)
    H.start()

    async def hud_connect():
        await asyncio.gather(
            HC.connect_hud(),
            HC.monitor_connection()
        )

    try:
        asyncio.run(hud_connect())
    finally:
        J.stop()
        H.stop()
        J.join()
        H.join()


if __name__ == '__main__':
    main()
