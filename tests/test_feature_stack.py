import contextlib
import io
import unittest

import feature_stack
from feature_stack import FeatureStack
from settings import DEFAULT_SETTINGS
from state import Dashboard


class FakeBatteryLogger:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash


class FeatureStackTests(unittest.TestCase):
    def test_feature_stack_wires_settings_into_handlers_and_buttons(self):
        dash = Dashboard()
        settings = DEFAULT_SETTINGS.copy()
        settings.update({
            'Logger': 0,
            'RearCenterBuckle': 2,
            'AutoRecirculation': 0,
            'KickDown': 0,
            'MarsMode': 1,
            'KeepWiperSpeed': 0,
            'SlowWiper': 0,
            'AltTurnSignal': 0,
            'AutoFollowingDistance': 1,
            'MapLampLeftShort': 'buckle_emulator',
            'MapLampLeftLong': 'mirror_fold',
            'MapLampLeftDouble': None,
            'MapLampRightShort': 'open_door_fl',
            'MapLampRightLong': 'open_door_rr,buckle_emulator',
            'MapLampRightDouble': 'open_door_fr,mars_mode_toggle',
        })

        sender = object()
        original_battery_logger = feature_stack.BatteryLogger
        feature_stack.BatteryLogger = FakeBatteryLogger
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                stack = FeatureStack(dash, settings, sender=sender)
        finally:
            feature_stack.BatteryLogger = original_battery_logger

        self.assertEqual(stack.logger.enabled, 0)
        self.assertEqual(stack.buckle.mode, 2)
        self.assertEqual(stack.fresh_air.enabled, 0)
        self.assertEqual(stack.kickdown.enabled, 0)
        self.assertEqual(stack.turn_signal.enabled, 0)
        self.assertEqual(stack.autopilot.mars_mode, 1)
        self.assertEqual(dash.ap.mars_mode, 1)
        self.assertEqual(stack.autopilot.keep_wiper_speed, 0)
        self.assertEqual(stack.autopilot.slow_wiper, 0)
        self.assertEqual(stack.autopilot.auto_distance, 1)
        self.assertIs(stack.autopilot.sender, sender)

        buttons = stack.button.buttons
        self.assertEqual(set(buttons), {'MapLampLeft', 'MapLampRight', 'ParkingButton'})
        self.assertEqual(buttons['MapLampLeft'].function_name['short'], 'buckle_emulator')
        self.assertEqual(buttons['MapLampLeft'].function_name['long'], 'mirror_fold')
        self.assertEqual(buttons['MapLampLeft'].function_name['double'], 'Undefined')
        self.assertEqual(buttons['MapLampRight'].function_name['short'], 'open_door_fl')
        self.assertEqual(buttons['MapLampRight'].function_name['long_park'], 'open_door_rr')
        self.assertEqual(buttons['MapLampRight'].function_name['long_drive'], 'buckle_emulator')
        self.assertEqual(buttons['MapLampRight'].function_name['double_park'], 'open_door_fr')
        self.assertEqual(buttons['MapLampRight'].function_name['double_drive'], 'mars_mode_toggle')
        self.assertEqual(buttons['ParkingButton'].function_name['long'], 'mirror_fold')


if __name__ == '__main__':
    unittest.main()
