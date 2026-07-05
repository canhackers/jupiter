import unittest

import functions
import packet_functions
import packets
import settings
import tesla
from can_registry import command, logging_address, monitoring_addrs, mux_address
from features import Autopilot, Button, ButtonManager, FreshAir, KickDown, RearCenterBuckle, Reboot, TurnSignal
from runtime import BatteryLogger, Buffer, Logger, csv_path
from state import Dashboard


class CompatibilityExportTests(unittest.TestCase):
    def test_packet_functions_reexports_packet_helpers(self):
        self.assertIs(packet_functions.calculate_checksum, packets.calculate_checksum)
        self.assertIs(packet_functions.get_value, packets.get_value)
        self.assertIs(packet_functions.make_new_packet, packets.make_new_packet)
        self.assertIs(packet_functions.modify_packet_value, packets.modify_packet_value)

    def test_functions_reexports_runtime_helpers(self):
        self.assertIs(functions.load_settings, settings.load_settings)
        self.assertIs(functions.json_file, settings.json_file)

    def test_tesla_reexports_legacy_symbols(self):
        self.assertIs(tesla.command, command)
        self.assertIs(tesla.logging_address, logging_address)
        self.assertIs(tesla.monitoring_addrs, monitoring_addrs)
        self.assertIs(tesla.mux_address, mux_address)
        self.assertIs(tesla.Autopilot, Autopilot)
        self.assertIs(tesla.Button, Button)
        self.assertIs(tesla.ButtonManager, ButtonManager)
        self.assertIs(tesla.FreshAir, FreshAir)
        self.assertIs(tesla.KickDown, KickDown)
        self.assertIs(tesla.RearCenterBuckle, RearCenterBuckle)
        self.assertIs(tesla.Reboot, Reboot)
        self.assertIs(tesla.TurnSignal, TurnSignal)
        self.assertIs(tesla.BatteryLogger, BatteryLogger)
        self.assertIs(tesla.Buffer, Buffer)
        self.assertIs(tesla.Logger, Logger)
        self.assertIs(tesla.csv_path, csv_path)
        self.assertIs(tesla.Dashboard, Dashboard)


if __name__ == '__main__':
    unittest.main()
