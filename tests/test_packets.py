import unittest

from packets import calculate_checksum, get_value, make_new_packet, modify_packet_value


class PacketHelperTests(unittest.TestCase):
    def test_modify_and_read_little_endian_field(self):
        packet = bytes(2)

        modified = modify_packet_value(packet, 0, 4, 0xA)

        self.assertEqual(get_value(modified, 0, 4), 0xA)
        self.assertEqual(packet, bytes(2))

    def test_signed_field_round_trip(self):
        packet = bytes(1)

        modified = modify_packet_value(packet, 0, 4, -1, signed=True)

        self.assertEqual(modified, b'\x0f')
        self.assertEqual(get_value(modified, 0, 4, signed=True), -1)

    def test_out_of_range_value_returns_original_packet(self):
        packet = b'\x12'

        modified = modify_packet_value(packet, 0, 4, 0x10)

        self.assertEqual(modified, packet)

    def test_make_new_packet_applies_changes_counter_and_checksum(self):
        packet = bytes(8)

        modified = make_new_packet(0x334, packet, [(5, 2, 1)])

        self.assertEqual(get_value(modified, 5, 2), 1)
        self.assertEqual(get_value(modified, 52, 4), 1)
        self.assertEqual(get_value(modified, 56, 8), calculate_checksum(0x334, modified))


if __name__ == '__main__':
    unittest.main()
