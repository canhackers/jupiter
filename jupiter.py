import os
import time
import can
import threading
from functions import initialize_canbus_connection
from tesla import Buffer, Dashboard, monitoring_addrs, FSD_Control


class Jupiter(threading.Thread):
    def __init__(self, dash):
        super().__init__()
        self.jupiter_online = True
        self.dash = dash

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

        #  부가 기능 로딩
        FSD_CONTROL = FSD_Control(BUFFER, self.dash)

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

                # 1초에 한번 전송되는 차량 시각 정보 수신
                if address in [0x3f8, 0x3fd]:
                    bus_connected = 1
                    signal = FSD_CONTROL.check(bus, address, signal)

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

if __name__ == '__main__':
    main()
