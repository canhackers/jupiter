import time

from packets import modify_packet_value


class FreshAir:
    def __init__(self, buffer, dash, enabled=0):
        self.buffer = buffer
        self.dash = dash
        self.enabled = enabled if enabled is not None else 0
        self.recirc_mode = 1
        # 마지막으로 Frseh로 바뀐 시간, 마지막으로 Recirc로 바뀐 시간
        self.last_mode_change = time.time()
        # n명 탑승 시 (a분 내기, b분 외기)
        self.time_dict = {0: (10, 5),
                          1: (10, 5),
                          2: (7, 8),
                          3: (5, 10),
                          4: (0, 1440),
                          5: (0, 1440)}

    def check(self, bus, address, byte_data):
        if not self.enabled:
            return byte_data
        if (bus == 0) and (address == 0x2f3):
            if self.dash.ui_hvac.recirc_mode == 0:
                ret = byte_data
                parameters = self.time_dict.get(self.dash.cabin.occupant_count)
                if parameters:
                    recirc_time, fresh_time = parameters
                else:
                    return byte_data
                now = time.time()
                elapsed = (now - self.last_mode_change)
                if (self.recirc_mode == 1) and (elapsed > (60 * recirc_time)):
                    # 내기 모드로 지정 시간을 넘었을 때
                    self.recirc_mode = 2
                    self.last_mode_change = now
                elif (self.recirc_mode == 2) and (elapsed > (60 * fresh_time)):
                    # 외기 모드로 지정 시간을 넘었을 때
                    self.recirc_mode = 1
                    self.last_mode_change = now
                if self.recirc_mode == 2:
                    ret = modify_packet_value(byte_data, 20, 2, self.recirc_mode)
                    self.buffer.write_message_buffer(bus, address, ret)
                return ret
        return byte_data
