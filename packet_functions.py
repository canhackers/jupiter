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


def modify_packet_value(packet_byte, start_bit, length, new_value):
    # 카운터와 체크섬이 없고, 특정 비트만 바꾸면 될 때 사용하는 함수
    try:
        byte_index = start_bit // 8
        bit_index = start_bit % 8
        if not (0 <= new_value < (1 << length)):
            # if new_value not fit in range
            return packet_byte
        mask = ((1 << length) - 1) << bit_index
        byte_array = bytearray(packet_byte)
        byte_array[byte_index] &= ~mask
        byte_array[byte_index] |= (new_value << bit_index)
        return bytes(byte_array)
    except:
        print('An error occurred in modify_packet_value')
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
