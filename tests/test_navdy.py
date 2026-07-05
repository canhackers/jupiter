import contextlib
import io
import sys
import types
import unittest

from state import Dashboard


fake_bluetooth = types.ModuleType('bluetooth')
fake_bluetooth.RFCOMM = object()
fake_bluetooth.find_service = lambda **kwargs: []


class FakeBluetoothSocket:
    def __init__(self, protocol):
        self.protocol = protocol
        self.sent = []

    def connect(self, address):
        self.address = address

    def send(self, payload):
        self.sent.append(payload)


fake_bluetooth.BluetoothSocket = FakeBluetoothSocket
sys.modules['bluetooth'] = fake_bluetooth

import navdy


class HudStateTests(unittest.TestCase):
    def test_update_connected_state_tracks_navdy_connection(self):
        dash = Dashboard()
        with contextlib.redirect_stdout(io.StringIO()):
            hud = navdy.Hud(dash)
        try:
            dash.device.navdy_connected = 1
            hud.navdy.connected = False

            self.assertFalse(hud._update_connected_state())
            self.assertEqual(dash.device.navdy_connected, 0)

            hud.navdy.connected = True

            self.assertTrue(hud._update_connected_state())
            self.assertEqual(dash.device.navdy_connected, 1)
        finally:
            hud.loop.close()


if __name__ == '__main__':
    unittest.main()
