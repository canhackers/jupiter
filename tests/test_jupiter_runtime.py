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
        stack = types.SimpleNamespace(
            button=FakeHandler('button', calls),
            turn_signal=FakeHandler('turn_signal', calls),
            autopilot=FakeHandler('autopilot', calls),
            buckle=FakeHandler('buckle', calls),
            reboot=FakeHandler('reboot', calls),
            kickdown=FakeHandler('kickdown', calls),
            fresh_air=FakeHandler('fresh_air', calls),
            battery_logger=types.SimpleNamespace(log_high_load=lambda torque: calls.append(f'high:{torque}')),
        )

        signal, last_high_load_log = self.jupiter._apply_feature_handlers(0, 0x3c2, b'', stack, 10.0, 0.0)

        self.assertEqual(calls, ['buckle', 'turn_signal', 'autopilot', 'reboot'])
        self.assertEqual(signal, b'btar')
        self.assertEqual(last_high_load_log, 0.0)

    def test_bus_watchdog_reinitializes_after_error(self):
        calls = []
        original_init = jupiter.initialize_canbus_connection
        jupiter.initialize_canbus_connection = lambda: calls.append('init')
        try:
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


if __name__ == '__main__':
    unittest.main()
