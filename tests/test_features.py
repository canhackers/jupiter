import contextlib
import io
import unittest

from features.drive import KickDown
from features.hvac import FreshAir
from features.safety import RearCenterBuckle
from features.signaling import TurnSignal
from features.system import Reboot
from packets import get_value, modify_packet_value
from state import Dashboard


class FakeBuffer:
    def __init__(self):
        self.message_buffer = []

    def write_message_buffer(self, bus, address, signal):
        self.message_buffer.append((bus, address, signal))


class FeatureCheckTests(unittest.TestCase):
    def test_kickdown_applies_sport_pedal_map_when_comfort_and_accelerating(self):
        buffer = FakeBuffer()
        dash = Dashboard()
        dash.drive_config.pedal_map = 0
        dash.di.accel_pedal_pos = 91
        feature = KickDown(buffer, dash, enabled=1)

        with contextlib.redirect_stdout(io.StringIO()):
            modified = feature.check(0, 0x334, bytes(8))

        self.assertEqual(get_value(modified, 5, 2), 1)
        self.assertEqual(buffer.message_buffer, [(0, 0x334, modified)])

    def test_kickdown_brake_clears_apply_state_without_mutating_brake_frame(self):
        buffer = FakeBuffer()
        dash = Dashboard()
        dash.ibst.driver_brake = 2
        feature = KickDown(buffer, dash, enabled=1)
        feature.apply = 1
        signal = b'12345678'

        with contextlib.redirect_stdout(io.StringIO()):
            modified = feature.check(0, 0x39d, signal)

        self.assertEqual(modified, signal)
        self.assertEqual(feature.apply, 0)
        self.assertEqual(buffer.message_buffer, [])

    def test_rear_center_buckle_mode_one_sets_center_belt_when_rear_side_is_occupied(self):
        buffer = FakeBuffer()
        dash = Dashboard()
        dash.features.buckle_emulator = 1
        dash.cabin.seat_occupancy_rl = 1
        dash.cabin.seat_occupancy_rc = 1
        feature = RearCenterBuckle(buffer, dash, mode=1)

        modified = feature.check(0, 0x3c2, bytes(8))

        self.assertEqual(get_value(modified, 62, 2), 2)
        self.assertEqual(buffer.message_buffer, [(0, 0x3c2, modified)])

    def test_fresh_air_requests_fresh_mode_when_recirc_window_expires(self):
        buffer = FakeBuffer()
        dash = Dashboard()
        dash.ui_hvac.recirc_mode = 0
        dash.cabin.occupant_count = 4
        feature = FreshAir(buffer, dash, enabled=1)
        feature.last_mode_change = 0

        modified = feature.check(0, 0x2f3, bytes(8))

        self.assertEqual(get_value(modified, 20, 2), 2)
        self.assertEqual(buffer.message_buffer, [(0, 0x2f3, modified)])

    def test_turn_signal_stalk_frame_is_generated_after_right_dial_request(self):
        buffer = FakeBuffer()
        dash = Dashboard()
        feature = TurnSignal(buffer, dash, enabled=1)
        dial_signal = modify_packet_value(bytes(8), 0, 2, 1)
        dial_signal = modify_packet_value(dial_signal, 8, 2, 2)

        feature.check(0, 0x3c2, dial_signal)
        modified = feature.check(0, 0x249, bytes(8))

        self.assertEqual(get_value(modified, 16, 4), 6)
        self.assertEqual(buffer.message_buffer, [(0, 0x249, modified)])

    def test_reboot_returns_original_payload_when_not_requested(self):
        dash = Dashboard()
        feature = Reboot(dash)
        signal = b'12345678'

        modified = feature.check(0, 0x3c2, signal)

        self.assertEqual(modified, signal)


if __name__ == '__main__':
    unittest.main()
