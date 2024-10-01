def get_value(packet_byte, loc, length, endian='little', signed=False):
    byte_index = loc // 8
    bit_index = loc % 8
    num_bytes = (loc + length + 7) // 8 - byte_index  # 필요한 전체 바이트 수

    if endian == 'little':
        # Little endian
        value = int.from_bytes(packet_byte[byte_index:byte_index + num_bytes], 'little')
        value >>= bit_index
    elif endian == 'big':
        # Big endian
        value = int.from_bytes(packet_byte[byte_index:byte_index + num_bytes], 'big')
        value >>= (8 * num_bytes - length - bit_index)
    else:
        print('endian 유형을 잘못 입력했습니다. little 또는 big을 사용하세요.')
        return packet_byte

    mask = (1 << length) - 1
    value &= mask

    if signed and (value & (1 << (length - 1))):
        # 음수값 처리: 2의 보수 계산
        value -= (1 << length)

    return value


def modify_packet_value(packet_byte, start_bit, length, new_value, endian='little', signed=False):
    try:
        # 바이트 배열로 변환
        byte_array = bytearray(packet_byte)

        # signed 처리를 위한 최대값과 최소값 계산
        if signed:
            min_value = -(1 << (length - 1))
            max_value = (1 << (length - 1)) - 1
        else:
            min_value = 0
            max_value = (1 << length) - 1

        # new_value가 허용 범위 내에 있는지 확인
        if not (min_value <= new_value <= max_value):
            return packet_byte

        # signed 값인 경우 2의 보수 표현으로 변환
        if signed and new_value < 0:
            new_value = (1 << length) + new_value

        # 전체 비트를 하나의 정수로 변환
        packet_int = int.from_bytes(byte_array, byteorder=endian)

        # 기존 값을 지우기 위해 마스크 생성
        mask = ((1 << length) - 1) << start_bit
        packet_int &= ~mask  # 해당 비트 필드를 0으로 클리어

        # 새로운 값 설정
        packet_int |= (new_value << start_bit) & mask

        # 수정된 값을 바이트 배열로 변환
        modified_bytes = packet_int.to_bytes(len(byte_array), byteorder=endian)
        return modified_bytes
    except Exception as e:
        print(f'An error occurred in modify_packet_value: {e}')
        return packet_byte


def calculate_checksum(frame_id, packet_byte):
    id_val = (str(hex(frame_id)) if type(frame_id) == int else frame_id)[2:].zfill(4)
    common_val = int(id_val[:2], 16) + int(id_val[2:], 16)
    return (sum(packet_byte[:-1]) + common_val) % 256


def make_new_packet(frame_id, packet, modify_list, counter_loc=52, counter_bit=4, checksum_loc=56, checksum_bit=8,
                    keep_counter=False):
    # 카운터와 체크섬이 존재하는 경우 변조에 사용하는 함수
    for loc, length, new_value in modify_list:
        packet = modify_packet_value(packet, loc, length, new_value)
    old_counter = get_value(packet, counter_loc, counter_bit)
    if keep_counter:
        new_counter = old_counter
    else:
        new_counter = (old_counter + 1) % (2 ** counter_bit)
    packet = modify_packet_value(packet, counter_loc, counter_bit, new_counter)
    new_checksum = calculate_checksum(frame_id, packet)
    packet = modify_packet_value(packet, checksum_loc, checksum_bit, new_checksum)
    return packet
