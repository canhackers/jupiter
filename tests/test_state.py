import unittest

from packets import modify_packet_value
from state import Dashboard


class DashboardUpdateTests(unittest.TestCase):
    def test_drive_system_status_updates_gear_and_accel(self):
        dash = Dashboard()
        signal = bytes(8)
        signal = modify_packet_value(signal, 21, 3, 4)
        signal = modify_packet_value(signal, 32, 8, 100)

        dash.update('DriveSystemStatus', signal)

        self.assertEqual(dash.di.gear, 4)
        self.assertEqual(dash.di.accel_pedal_pos, 40.0)

    def test_powertrain_control_updates_pedal_map(self):
        dash = Dashboard()
        signal = modify_packet_value(bytes(8), 5, 2, 1)

        dash.update('UI_powertrainControl', signal)

        self.assertEqual(dash.drive_config.pedal_map, 1)

    def test_speed_update_clamps_to_non_negative_value(self):
        dash = Dashboard()
        signal = modify_packet_value(bytes(8), 24, 9, 123)

        dash.update('DIspeed', signal)

        self.assertEqual(dash.di.speed, 123)

    def test_seat_occupancy_updates_named_seats_and_count(self):
        dash = Dashboard()
        left_signal = bytes(8)
        for loc in (50, 56, 54, 58):
            left_signal = modify_packet_value(left_signal, loc, 2, 2)
        right_signal = modify_packet_value(bytes(8), 40, 2, 2)

        dash.update('VCLEFT_switchStatus', left_signal)
        dash.update('VCRIGHT_switchStatus', right_signal)

        self.assertEqual(dash.cabin.seat_occupancy_fl, 1)
        self.assertEqual(dash.cabin.seat_occupancy_fr, 1)
        self.assertEqual(dash.cabin.seat_occupancy_rl, 1)
        self.assertEqual(dash.cabin.seat_occupancy_rc, 1)
        self.assertEqual(dash.cabin.seat_occupancy_rr, 1)
        self.assertEqual(dash.cabin.occupant_count, 5)

    def test_unix_time_updates_raw_time_and_clock_string(self):
        dash = Dashboard()

        dash.update('UnixTime', (1).to_bytes(4, 'big'))

        self.assertEqual(dash.di.unix_time, 1)
        self.assertIsNotNone(dash.di.clock)


if __name__ == '__main__':
    unittest.main()
