import os
import time
import can
import threading
import asyncio
from functions import initialize_canbus_connection, load_settings
from tesla import Buffer, Dashboard, Logger, Autopilot, RearCenterBuckle, MapLampControl, FreshAir, \
    KickDown, TurnSignal, monitoring_addrs
from vcgencmd import Vcgencmd

vcgm = Vcgencmd()
DASH = Dashboard()
lock = threading.Lock()


class Jupiter(threading.Thread):
    def __init__(self):
        super().__init__()
        self.jupiter_online = True

    def run(self):
        if not self.jupiter_online:
            return False
        # CAN Bus Device 초기화
        initialize_canbus_connection()
        can_bus = can.interface.Bus(channel='can0', interface='socketcan')
        bus_connected = 0
        bus_error = 0
        DASH.bus_error_count = 0
        last_recv_time = time.time()
        bus = 0  # 라즈베리파이는 항상 0, panda는 다채널이므로 수신하면서 확인

        # 핵심 기능 로딩
        settings = load_settings()
        BUFFER = Buffer()
        LOGGER = Logger(BUFFER, DASH, cloud=0, enabled=settings.get('Logger'))

        #  부가 기능 로딩
        AP = Autopilot(BUFFER, DASH,
                       sender=can_bus,
                       device='raspi',
                       mars_mode=settings.get('MarsMode'),
                       keep_wiper_speed=settings.get('KeepWiperSpeed'),
                       slow_wiper=settings.get('SlowWiper'),
                       auto_distance=settings.get('AutoFollowingDistance'))

        BUCKLE = RearCenterBuckle(BUFFER, mode=settings.get('RearCenterBuckle'))
        MAPLAMP = MapLampControl(BUFFER, DASH, device='raspi',
                                 left=settings.get('MapLampLeft'),
                                 right=settings.get('MapLampRight'))
        FRESH = FreshAir(BUFFER, DASH, enabled=settings.get('AutoRecirculation'))
        KICKDOWN = KickDown(BUFFER, DASH, enabled=settings.get('KickDown'))
        TURNSIGNAL = TurnSignal(BUFFER, DASH, enabled=settings.get('AltTurnSignal'))
        TICK = False  # 차에서 1초 간격 Unix Time을 보내주는 타이밍인지 여부

        while True:
            current_time = time.time()
            DASH.current_time = current_time
            if (bus_connected == 1):
                if DASH.bus_error_count > 5:
                    print('Bus Error Count Over, reboot')
                    os.system('sudo reboot')
                if bus_error == 1:
                    DASH.bus_error_count += 1
                    print(f'Bus Error, {DASH.bus_error_count}')
                    initialize_canbus_connection()
                    can_bus = can.interface.Bus(channel='can0', interface='socketcan')
                    try:
                        AP.sender = can_bus
                        if DASH.occupancy == 1:
                            AP.volume_updown()
                    except:
                        pass
                    bus_error = 0
                else:
                    if (current_time - last_recv_time >= 5):
                        print('bus error counted')
                        DASH.bus_error_count += 1
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
                    DASH.update(dash_item, signal)
                DASH.last_update = current_time

                ### 기어 상태 체크 / 로깅 시작 ###
                if address == 0x118 and (DASH.clock is not None):
                    DASH.update('DriveSystemStatus', signal)
                    if (DASH.gear == 4) and (DASH.parked):  # Drive
                        print(f'Drive Gear Detected... Recording Drive history from {DASH.clock}')
                        DASH.parked = 0
                        DASH.drive_start_time = current_time
                        LOGGER.initialize()
                    elif (DASH.gear == 1) and (not DASH.parked):  # Park
                        print('Parking Gear Detected... Saving Drive history')
                        DASH.parked = 1
                        DASH.drive_start_time = 0
                        LOGGER.close()
                    else:
                        pass

                # 1초에 한번 전송되는 차량 시각 정보 수신
                if address == 0x528:
                    TICK = True
                    bus_connected = 1
                    DASH.update('UnixTime', signal)
                else:
                    TICK = False

                # 매 1초마다 실행할 액션 지정
                if TICK:
                    DASH.device_temp = vcgm.measure_temp()
                    print(f'Clock: {DASH.clock}  Temperature: {DASH.device_temp}')

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
                if DASH.occupancy == 0:
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


class HudConnector:
    def __init__(self):
        self.connected = asyncio.Event()
        self.connect_try_cnt = 0
        from navdy import Navdy
        try:
            with open('/home/mac_address', 'r') as f:
                mac_address = (f.readline()).strip()
            self.mac_address = mac_address
            self.NAVDY = Navdy(mac_address)
            self.init = True
        except Exception as e:
            print(e)
            self.mac_address = 'Not Available'
            self.NAVDY = Navdy('00:00:00:00:00:00')
            print('Can not find Navdy MAC Address file. check /home/mac_address')
            self.init = False

    async def connect_hud(self):
        while self.init:
            if not self.connected.is_set():
                self.connect_try_cnt += 1
                print(f'Attempting to connect to Navdy...{self.connect_try_cnt}')
                self.NAVDY.connected = self.NAVDY.connect()
                if self.NAVDY.connected:
                    print('Navdy Connected ', self.NAVDY.mac_address)
                    self.connected.set()
                    self.connect_try_cnt = 0
            await asyncio.sleep(5)

    async def monitor_connection(self):
        while self.init:
            if self.connected.is_set():
                await asyncio.sleep(5)
                if self.NAVDY.connected == False:
                    print('NAVDY 접속이 끊겼습니다')
                    self.connected.clear()
            await asyncio.sleep(1)

    def stop(self):
        self.init = False


class Hud(threading.Thread):
    def __init__(self, connector):
        super().__init__()
        self.connector = connector
        self.NAVDY = self.connector.NAVDY
        self.thread_online = True
        self.loop = None

    def run(self):
        last_update_fast = 0
        last_update_slow = 0
        while self.thread_online:
            if not self.NAVDY.connected:
                time.sleep(5)
                continue
            time.sleep(0.2)
            current_time = DASH.current_time
            try:
                if (current_time - last_update_fast) >= 0.2:
                    last_update_fast = current_time
                    if DASH.parked:
                        gear = 1
                    else:
                        if DASH.autopilot == 1:
                            gear = 6 if DASH.nag_disabled == 1 else 5
                        else:
                            gear = DASH.gear
                    payload = {'__speed__': DASH.ui_speed,
                               '__tachometer__': abs(DASH.torque_front + DASH.torque_rear),
                               'gear': gear
                               }
                    if (current_time - last_update_slow) >= 2:
                        last_update_slow = current_time
                        payload['voltage'] = DASH.LVB_voltage
                        payload['soc'] = DASH.soc
                        payload['hv_temp'] = DASH.HVB_max_temp
                        payload['ui_range'] = DASH.ui_range
                        payload['ui_range_map'] = DASH.ui_range
                        payload['raspi_temp'] = DASH.device_temp
                    self.NAVDY.send_message(payload)
            except Exception as e:
                print("Exception caught while processing Navdy Dash", e)

    def stop(self):
        self.thread_online = False

def main():
    J = Jupiter()
    HC = HudConnector()
    H = Hud(HC)

    J.start()
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
