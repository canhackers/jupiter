from features import Autopilot, ButtonManager, FreshAir, KickDown, RearCenterBuckle, Reboot, TurnSignal
from runtime import BatteryLogger, Buffer, Logger


class FeatureStack:
    def __init__(self, dash, settings, sender):
        self.buffer = Buffer()
        self.logger = Logger(self.buffer, dash, cloud=0, enabled=settings.get('Logger'))
        self.battery_logger = BatteryLogger(self.buffer, dash)

        self.autopilot = Autopilot(
            self.buffer,
            dash,
            sender=sender,
            device='raspi',
            mars_mode=settings.get('MarsMode'),
            keep_wiper_speed=settings.get('KeepWiperSpeed'),
            slow_wiper=settings.get('SlowWiper'),
            auto_distance=settings.get('AutoFollowingDistance'),
        )
        self.buckle = RearCenterBuckle(self.buffer, dash, mode=settings.get('RearCenterBuckle'))
        self.fresh_air = FreshAir(self.buffer, dash, enabled=settings.get('AutoRecirculation'))
        self.kickdown = KickDown(self.buffer, dash, enabled=settings.get('KickDown'))
        self.turn_signal = TurnSignal(self.buffer, dash, enabled=settings.get('AltTurnSignal'))
        self.reboot = Reboot(dash)
        self.button = ButtonManager(self.buffer, dash)
        self._configure_buttons(settings)

    def _configure_buttons(self, settings):
        self.button.add_button(btn_name='MapLampLeft')
        self.button.add_button(btn_name='MapLampRight')
        self.button.add_button(btn_name='ParkingButton', long_time=0.5)

        buttons_define = (
            ('MapLampLeft', 'short', settings.get('MapLampLeftShort')),
            ('MapLampLeft', 'long', settings.get('MapLampLeftLong')),
            ('MapLampLeft', 'double', settings.get('MapLampLeftDouble')),
            ('MapLampRight', 'short', settings.get('MapLampRightShort')),
            ('MapLampRight', 'long', settings.get('MapLampRightLong')),
            ('MapLampRight', 'double', settings.get('MapLampRightDouble')),
            ('ParkingButton', 'long', 'mirror_fold'),
        )
        for btn, ptype, func in buttons_define:
            if isinstance(func, str):
                functions = func.split(',')
                if len(functions) == 1:
                    self.button.assign(btn_name=btn, press_type=ptype, function_name=functions[0].strip())
                else:
                    self.button.assign(btn_name=btn, press_type=ptype + '_park', function_name=functions[0].strip())
                    self.button.assign(btn_name=btn, press_type=ptype + '_drive', function_name=functions[1].strip())
