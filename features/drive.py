from packets import make_new_packet


class KickDown:
    def __init__(self, buffer, dash, enabled=0):
        self.buffer = buffer
        self.dash = dash
        self.enabled = enabled if enabled is not None else 0
        self.apply = 0

    def check(self, bus, address, byte_data):
        if not self.enabled:
            return byte_data
        if (bus == 0) and (address == 0x39d):
            if self.dash.ibst.driver_brake == 2:
                if self.apply:
                    print('Brake Pressed, Kick Down mode disabled')
                    self.apply = 0

        if (bus == 0) and (address == 0x334):
            if (self.dash.drive_config.pedal_map == 0) and (self.dash.di.accel_pedal_pos > 90) and (not self.apply):
                print('------- Kick Down / Sports Mode On -------')
                self.apply = 1
            if self.apply:
                ret = make_new_packet(0x334, byte_data, [(5, 2, 1)])
                self.buffer.write_message_buffer(bus, address, ret)
                return ret

        return byte_data
