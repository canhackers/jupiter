import contextlib
import io
import sys
import types
import unittest

from state import Dashboard


fake_bleak = types.ModuleType('bleak')
fake_bleak.BleakScanner = object
fake_bleak.BleakClient = object
sys.modules['bleak'] = fake_bleak

import beacon


class HolyIotTests(unittest.TestCase):
    def test_notification_handler_updates_device_beacon_state(self):
        dash = Dashboard()
        dash.device.beacon = {'1': 0}
        holy = beacon.HolyIoT(dash)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                holy.notification_handler(None, b'\x01', '1')
            self.assertEqual(dash.device.beacon['1'], 1)

            with contextlib.redirect_stdout(io.StringIO()):
                holy.notification_handler(None, b'\x00', '1')
            self.assertEqual(dash.device.beacon['1'], 0)
        finally:
            holy.loop.close()


if __name__ == '__main__':
    unittest.main()
