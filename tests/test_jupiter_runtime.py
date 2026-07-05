import contextlib
import io
import sys
import types
import unittest

from state import Dashboard


sent_messages = []


class FakeMessage:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeCanBus:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message.kwargs)
        sent_messages.append(message.kwargs)


class FakeRecvCanBus:
    def recv(self, timeout):
        return types.SimpleNamespace(
            arbitration_id=0x528,
            data=(1).to_bytes(4, 'big'),
        )

    def send(self, message):
        pass


fake_can = types.ModuleType('can')
fake_can.Message = FakeMessage
fake_can.interface = types.SimpleNamespace(Bus=lambda **kwargs: FakeCanBus())
sys.modules['can'] = fake_can

fake_vcgencmd = types.ModuleType('vcgencmd')
fake_vcgencmd.Vcgencmd = object
sys.modules['vcgencmd'] = fake_vcgencmd

import jupiter
from jupiter import Jupiter


class FakeBuffer:
    def __init__(self):
        self.message_buffer = [(0, 0x123, b'12345678')]
        self.flushes = 0

    def flush_message_buffer(self):
        self.flushes += 1
        self.message_buffer = []


class FakeHandler:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    def check(self, bus, address, signal):
        self.calls.append(self.name)
        return signal + self.name[:1].encode('ascii')


class JupiterRuntimeHelperTests(unittest.TestCase):
    def setUp(self):
        sent_messages.clear()
        self.jupiter = object.__new__(Jupiter)
        self.jupiter.dash = Dashboard()
        self.jupiter.settings = {}

    def make_feature_stack(self, calls):
        return types.SimpleNamespace(
            button=FakeHandler('button', calls),
            turn_signal=FakeHandler('turn_signal', calls),
            autopilot=FakeHandler('autopilot', calls),
            buckle=FakeHandler('buckle', calls),
            reboot=FakeHandler('reboot', calls),
            kickdown=FakeHandler('kickdown', calls),
            fresh_air=FakeHandler('fresh_air', calls),
            battery_logger=types.SimpleNamespace(log_high_load=lambda torque: calls.append(f'high:{torque}')),
        )

    def test_send_buffered_messages_sends_when_occupied_and_flushes(self):
        buffer = FakeBuffer()
        bus = FakeCanBus()

        bus_error = self.jupiter._send_buffered_messages(bus, buffer)

        self.assertFalse(bus_error)
        self.assertEqual(len(bus.sent), 1)
        self.assertEqual(bus.sent[0]['arbitration_id'], 0x123)
        self.assertEqual(buffer.flushes, 1)

    def test_send_buffered_messages_skips_send_when_unoccupied_and_flushes(self):
        buffer = FakeBuffer()
        bus = FakeCanBus()
        self.jupiter.dash.cabin.is_occupied = 0

        bus_error = self.jupiter._send_buffered_messages(bus, buffer)

        self.assertFalse(bus_error)
        self.assertEqual(bus.sent, [])
        self.assertEqual(buffer.flushes, 1)

    def test_apply_feature_handlers_preserves_3c2_order(self):
        calls = []
        stack = self.make_feature_stack(calls)

        signal, last_high_load_log = self.jupiter._apply_feature_handlers(0, 0x3c2, b'', stack, 10.0, 0.0)

        self.assertEqual(calls, ['buckle', 'turn_signal', 'autopilot', 'reboot'])
        self.assertEqual(signal, b'btar')
        self.assertEqual(last_high_load_log, 0.0)

    def test_apply_feature_handlers_preserves_address_orders(self):
        cases = (
            (0x1f9, ['button']),
            (0x229, ['button', 'autopilot']),
            (0x249, ['turn_signal']),
            (0x273, ['autopilot', 'button']),
            (0x2f3, ['fresh_air']),
            (0x334, ['kickdown']),
            (0x39d, ['autopilot', 'kickdown']),
            (0x3e2, ['button']),
        )

        for address, expected_calls in cases:
            with self.subTest(address=hex(address)):
                calls = []
                stack = self.make_feature_stack(calls)

                signal, last_high_load_log = self.jupiter._apply_feature_handlers(
                    0,
                    address,
                    b'',
                    stack,
                    10.0,
                    0.0,
                )

                self.assertEqual(calls, expected_calls)
                self.assertEqual(signal, b''.join(name[:1].encode('ascii') for name in expected_calls))
                self.assertEqual(last_high_load_log, 0.0)

    def test_apply_feature_handlers_logs_high_load_with_cooldown(self):
        self.jupiter.dash.powertrain.torque_front = 1200
        self.jupiter.dash.powertrain.torque_rear = -900
        calls = []
        stack = self.make_feature_stack(calls)

        signal, last_high_load_log = self.jupiter._apply_feature_handlers(0, 0x108, b'raw', stack, 10.0, 9.0)
        self.assertEqual(calls, ['high:2100'])
        self.assertEqual(signal, b'raw')
        self.assertEqual(last_high_load_log, 10.0)

        calls.clear()
        signal, last_high_load_log = self.jupiter._apply_feature_handlers(0, 0x186, b'raw', stack, 10.2, 10.0)
        self.assertEqual(calls, [])
        self.assertEqual(signal, b'raw')
        self.assertEqual(last_high_load_log, 10.0)

    def test_bus_watchdog_reinitializes_after_error(self):
        calls = []
        original_init = jupiter.initialize_canbus_connection
        jupiter.initialize_canbus_connection = lambda: calls.append('init')
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                new_bus, bus_error, last_recv_time = self.jupiter._handle_bus_watchdog(
                    object(),
                    bus_connected=1,
                    bus_error=1,
                    current_time=100.0,
                    last_recv_time=95.0,
                )
        finally:
            jupiter.initialize_canbus_connection = original_init

        self.assertIsInstance(new_bus, FakeCanBus)
        self.assertEqual(bus_error, 0)
        self.assertEqual(last_recv_time, 95.0)
        self.assertEqual(self.jupiter.dash.runtime.bus_error_count, 1)
        self.assertEqual(calls, ['init'])

    def test_run_processes_first_received_frame_with_feature_stack_button(self):
        calls = []

        class FakeRuntimeBuffer:
            def __init__(self):
                self.message_buffer = []

            def write_can_buffer(self, bus, address, signal):
                calls.append(('buffer', address, signal))

            def flush_message_buffer(self):
                calls.append('flush')

        class FakeRuntimeLogger:
            file = None

            def initialize(self):
                calls.append('logger_initialize')

            def close(self):
                calls.append('logger_close')

            def write(self):
                calls.append('logger_write')

        class FakeBatteryLogger:
            def log_health(self, event_type):
                calls.append(('health', event_type))

            def log_dynamics(self):
                calls.append('dynamics')

            def log_high_load(self, torque):
                calls.append(('high_load', torque))

        class FakeAutopilot:
            def tick(self):
                calls.append('tick')

        class FakeRuntimeFeatureStack:
            def __init__(self, dash, settings, sender):
                self.buffer = FakeRuntimeBuffer()
                self.logger = FakeRuntimeLogger()
                self.battery_logger = FakeBatteryLogger()
                self.autopilot = FakeAutopilot()
                self.button = FakeHandler('button', calls)
                self.turn_signal = FakeHandler('turn_signal', calls)
                self.fresh_air = FakeHandler('fresh_air', calls)
                self.kickdown = FakeHandler('kickdown', calls)
                self.buckle = FakeHandler('buckle', calls)
                self.reboot = FakeHandler('reboot', calls)

        def stop_after_first_send(self, can_bus, buffer):
            calls.append('send')
            raise StopIteration

        runner = object.__new__(Jupiter)
        runner.jupiter_online = True
        runner.dash = Dashboard()
        runner.settings = {}
        runner.vcgm = types.SimpleNamespace(measure_temp=lambda: 0)

        original_init = jupiter.initialize_canbus_connection
        original_bus = jupiter.can.interface.Bus
        original_feature_stack = jupiter.FeatureStack
        original_send = Jupiter._send_buffered_messages
        jupiter.initialize_canbus_connection = lambda: calls.append('init')
        jupiter.can.interface.Bus = lambda **kwargs: FakeRecvCanBus()
        jupiter.FeatureStack = FakeRuntimeFeatureStack
        Jupiter._send_buffered_messages = stop_after_first_send
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(StopIteration):
                    runner.run()
        finally:
            jupiter.initialize_canbus_connection = original_init
            jupiter.can.interface.Bus = original_bus
            jupiter.FeatureStack = original_feature_stack
            Jupiter._send_buffered_messages = original_send

        self.assertIn(('buffer', 0x528, (1).to_bytes(4, 'big')), calls)
        self.assertIn('tick', calls)
        self.assertIn('send', calls)


if __name__ == '__main__':
    unittest.main()
