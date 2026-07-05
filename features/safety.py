from packets import get_value, modify_packet_value


class RearCenterBuckle:
    def __init__(self, buffer, dash, mode=0):
        self.buffer = buffer
        self.mode = mode if mode is not None else 0
        self.dash = dash
        # mode: 0/None - 비활성화, 1 - 뒷좌석 중앙만, 2 - 모두

    def check(self, bus, address, byte_data):
        ret = byte_data
        if (not self.mode) or (self.dash.features.buckle_emulator == 0):
            return ret

        if bus == 0 and address == 0x3c2:
            mux = get_value(ret, loc=0, length=2, endian='little', signed=False)
            if mux == 0:
                if self.mode == 1:
                    # 뒷좌석 좌, 우 어느 한 쪽에 사람이 앉아 있는 상태에서 가운데에 착좌가 인식되는 경우 안전벨트 스위치 켜기
                    if self.dash.cabin.seat_occupancy_rl == 1 or self.dash.cabin.seat_occupancy_rr == 1:
                        if self.dash.cabin.seat_occupancy_rc == 1:
                            ret = modify_packet_value(ret, 62, 2, 2)
                            self.buffer.write_message_buffer(bus, address, ret)
                elif self.mode == 2:
                    # ★★★ Warning : 뒷좌석 안전벨트 미착용 상태로 승객을 태우는 것은 매우 위험하며, 도로교통법 위반입니다. ★★★★
                    # 짐을 쌓은 상태로 부득이 정리가 어려운 경우에만 사용하세요.
                    ret = modify_packet_value(ret, 54, 2, 1)
                    ret = modify_packet_value(ret, 62, 2, 2)
                    # Disable rearLeftOccupancySwitch
                    ret = modify_packet_value(ret, 56, 2, 1)
                    # Disable rearRightOccupancySwitch
                    ret = modify_packet_value(ret, 58, 2, 1)
                    self.buffer.write_message_buffer(bus, address, ret)
        return ret
