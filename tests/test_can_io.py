import contextlib
import io
import unittest

import can_io


class CanIoTests(unittest.TestCase):
    def test_initialize_canbus_connection_runs_legacy_command_sequence(self):
        calls = []
        original_system = can_io.os.system
        can_io.os.system = lambda command: calls.append(command) or 0
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                initialized = can_io.initialize_canbus_connection()
        finally:
            can_io.os.system = original_system

        self.assertTrue(initialized)
        self.assertEqual(calls, [
            'sudo modprobe -r mcp251x',
            'sudo modprobe mcp251x',
            'sudo ip link set can0 type can bitrate 500000',
            'sudo ifconfig can0 down',
            'sudo ifconfig can0 up',
        ])

    def test_initialize_canbus_connection_returns_false_when_command_raises(self):
        original_system = can_io.os.system
        can_io.os.system = lambda command: (_ for _ in ()).throw(RuntimeError(command))
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                initialized = can_io.initialize_canbus_connection()
        finally:
            can_io.os.system = original_system

        self.assertFalse(initialized)


if __name__ == '__main__':
    unittest.main()
