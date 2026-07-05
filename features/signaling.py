import time

from packets import get_value, modify_packet_value


class TurnSignal:
    def __init__(self, buffer, dash, enabled=0):
        # up = right = 4,  down = left = 8
        self.crc_right = (163, 208, 18, 235, 235, 187, 116, 102, 7, 102, 218, 16, 2, 43, 151, 246)
        self.crc_right_half = (135, 244, 54, 207, 207, 159, 80, 66, 35, 66, 254, 52, 38, 15, 179, 210)
        self.crc_left = (235, 152, 90, 163, 163, 243, 60, 46, 79, 46, 146, 88, 74, 99, 223, 190)
        self.crc_left_half = (191, 204, 14, 247, 247, 167, 104, 122, 27, 122, 198, 12, 30, 55, 139, 234)
        self.buffer = buffer
        self.dash = dash
        self.enabled = enabled if enabled is not None else 0
        self.dash.features.alt_turn_signal = self.enabled
        self.turn_indicator = 0  # 8 = left, 4 = right, 6 = left half, 2 = right half
        self.right_dial_click_time = 0

    def check(self, bus, address, byte_data):
        if not self.enabled:
            return byte_data
        if (bus == 0) and (address == 0x249):
            if self.turn_indicator == 0:
                return byte_data
            else:
                ret = byte_data
                counter = (get_value(byte_data, 8, 4) + 1) % (2 ** 4)
                if self.turn_indicator == 8:
                    crc = self.crc_left[counter]
                elif self.turn_indicator == 6:
                    crc = self.crc_left_half[counter]
                elif self.turn_indicator == 4:
                    crc = self.crc_right[counter]
                elif self.turn_indicator == 2:
                    crc = self.crc_right_half[counter]
                else:
                    crc = None
                if crc is not None:
                    ret = modify_packet_value(ret, 8, 4, counter)
                    ret = modify_packet_value(ret, 16, 4, self.turn_indicator)
                    ret = modify_packet_value(ret, 0, 8, crc)
                    self.buffer.write_message_buffer(bus, address, ret)
            return ret

        if (bus == 0) and (address == 0x3c2):
            if ((self.dash.ap.autopilot == 1) or (self.dash.ap.tacc == 1)) and (self.dash.ap.turn_signal_on_ap == 0):
                self.turn_indicator = 0
                return byte_data
            if get_value(byte_data, 0, 2) == 1:
                if get_value(byte_data, 8, 2) == 2:
                    self.right_dial_click_time = time.time()
                    if self.dash.ap.turn_signal_on_ap:
                        if self.dash.body.turn_indicator_right or self.dash.body.turn_indicator_left:
                            # 이미 방향지시등이 켜져 있는 경우는 취소하기 위한 얕은 클릭으로 동작
                            self.turn_indicator = 6
                        else:
                            # 오토파일럿 중에는 깊게 눌러야 함
                            self.turn_indicator = 8
                    else:
                        self.turn_indicator = 6
                elif get_value(byte_data, 10, 2) == 2:
                    self.right_dial_click_time = time.time()
                    if self.dash.ap.turn_signal_on_ap:
                        if self.dash.body.turn_indicator_right or self.dash.body.turn_indicator_left:
                            self.turn_indicator = 2
                        else:
                            self.turn_indicator = 4
                    else:
                        self.turn_indicator = 2
                else:
                    if self.turn_indicator != 0:
                        if time.time() - self.right_dial_click_time > 0.1:
                            # indicator 동작 신호 지속시간이 있어야 방향지시등이 동작함
                            self.turn_indicator = 0
            return byte_data
        return byte_data
