import os
import time
import can
import threading
from vcgencmd import Vcgencmd
from can_io import initialize_canbus_connection
from can_registry import monitoring_addrs
from feature_stack import FeatureStack
from settings import load_settings
from state import Dashboard


# 기존 순차 payload 변조 순서를 보존한다.
FEATURE_HANDLER_ORDER = {
    0x1f9: ('button',),
    0x229: ('button', 'autopilot'),
    0x249: ('turn_signal',),
    0x273: ('autopilot', 'button'),
    0x2f3: ('fresh_air',),
    0x334: ('kickdown',),
    0x39d: ('autopilot', 'kickdown'),
    0x3c2: ('buckle', 'turn_signal', 'autopilot', 'reboot'),
    0x3e2: ('button',),
}

HIGH_LOAD_LOG_ADDRESSES = {0x108, 0x186}


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
        self.dash.runtime.bus_error_count = 0
        last_recv_time = time.time()
        bus = 0  # 라즈베리파이는 항상 0, panda는 다채널이므로 수신하면서 확인

        # 핵심 기능 로딩
        feature_stack = FeatureStack(self.dash, self.settings, can_bus)
        BUFFER = feature_stack.buffer
        LOGGER = feature_stack.logger
        BAT_LOGGER = feature_stack.battery_logger
        dynamic_log_timer = 0
        last_high_load_log = 0

        autopilot = feature_stack.autopilot

        while True:
            current_time = time.time()
            self.dash.runtime.current_time = current_time
            can_bus, bus_error, last_recv_time = self._handle_bus_watchdog(
                can_bus,
                bus_connected,
                bus_error,
                current_time,
                last_recv_time,
            )

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
                self.dash.runtime.last_update = current_time

                self._handle_drive_transition(address, signal, LOGGER, BAT_LOGGER, BUTTON)
                bus_connected, dynamic_log_timer = self._handle_tick(
                    address,
                    signal,
                    bus_connected,
                    dynamic_log_timer,
                    LOGGER,
                    BAT_LOGGER,
                    autopilot,
                )

                signal, last_high_load_log = self._apply_feature_handlers(
                    bus,
                    address,
                    signal,
                    feature_stack,
                    current_time,
                    last_high_load_log,
                )

            ###################################################
            ############ 파트2. 메시지를 보내는 영역 ##############
            ###################################################

            if self._send_buffered_messages(can_bus, BUFFER):
                bus_error = 1

    def stop(self):
        self.jupiter_online = False

    def _handle_drive_transition(self, address, signal, logger, battery_logger, button):
        if address == 0x118 and (self.dash.di.clock is not None):
            self.dash.update('DriveSystemStatus', signal)
            if self.dash.di.gear == 4:
                if self.dash.di.parked == 1:   # Park(1) -> Drive(4)
                    print(f'Drive Gear Detected... Recording Drive history from {self.dash.di.clock}')
                    self.dash.di.parked = 0
                    self.dash.di.drive_time = 0
                    self.dash.di.drive_finished = 0
                    logger.initialize()
                    battery_logger.log_health("DRIVE_START")
            elif self.dash.di.gear == 1:
                if self.dash.di.parked == 0:  # Drive(4) -> Park(1)
                    print('Parking Gear Detected... Saving Drive history')
                    self.dash.di.parked = 1
                    self.dash.di.drive_time = 0
                    self.dash.di.drive_finished = 1
                    logger.close()
                    battery_logger.log_health("DRIVE_END")
                if self.settings.get('MirrorAutoFold'):
                    if self.dash.cabin.occupant_count == 0 and self.dash.di.drive_finished == 1:
                        button.mirror_request = 1
                        self.dash.di.drive_finished = 0

    def _handle_bus_watchdog(self, can_bus, bus_connected, bus_error, current_time, last_recv_time):
        if bus_connected == 1:
            if self.dash.runtime.bus_error_count > 5:
                print('Bus Error Count Over, reboot')
                os.system('sudo reboot')
            if bus_error == 1:
                self.dash.runtime.bus_error_count += 1
                print(f'Bus Error, {self.dash.runtime.bus_error_count}')
                initialize_canbus_connection()
                can_bus = can.interface.Bus(channel='can0', interface='socketcan')
                bus_error = 0
            else:
                if current_time - last_recv_time >= 5:
                    print('bus error counted')
                    bus_error = 1
                    self.dash.runtime.bus_error_count += 1
                    last_recv_time = time.time()
        elif bus_connected == 0 and current_time - last_recv_time >= 10:
            print('Waiting until CAN Bus Connecting...',
                  time.strftime('%m/%d %H:%M:%S', time.localtime(last_recv_time)))
            initialize_canbus_connection()
            last_recv_time = time.time()
        return can_bus, bus_error, last_recv_time

    def _handle_tick(self, address, signal, bus_connected, dynamic_log_timer, logger, battery_logger, autopilot):
        if address != 0x528:
            return bus_connected, dynamic_log_timer

        bus_connected = 1
        self.dash.update('UnixTime', signal)
        self.dash.device.temperature = self.vcgm.measure_temp()
        if self.dash.di.gear == 4:
            self.dash.di.drive_time += 1
            dynamic_log_timer += 1
            if dynamic_log_timer >= 300:  # 300초(5분) 경과 시
                battery_logger.log_dynamics()
                dynamic_log_timer = 0
        print(f'Clock: {self.dash.di.clock}  Temperature: {self.dash.device.temperature}')

        if logger.file is not None:
            logger.write()

        autopilot.tick()
        return bus_connected, dynamic_log_timer

    def _apply_feature_handlers(self, bus, address, signal, feature_stack, current_time, last_high_load_log):
        for handler_name in FEATURE_HANDLER_ORDER.get(address, ()):
            handler = getattr(feature_stack, handler_name)
            signal = handler.check(bus, address, signal)

        if address in HIGH_LOAD_LOG_ADDRESSES:
            total_torque = abs(self.dash.powertrain.torque_front) + abs(self.dash.powertrain.torque_rear)
            if total_torque > 2000 and (current_time - last_high_load_log > 0.5):
                feature_stack.battery_logger.log_high_load(total_torque)
                last_high_load_log = current_time
        return signal, last_high_load_log

    def _send_buffered_messages(self, can_bus, buffer):
        try:
            if self.dash.cabin.is_occupied != 0:
                for _, address, signal in buffer.message_buffer:
                    can_bus.send(can.Message(arbitration_id=address,
                                             channel='can0',
                                             data=bytearray(signal),
                                             dlc=len(bytearray(signal)),
                                             is_extended_id=False))
        except Exception as e:
            print("메시지 발신 실패, Can Bus 리셋 시도 \n", e)
            return True
        finally:
            buffer.flush_message_buffer()
        return False


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
