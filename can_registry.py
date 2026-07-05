logging_address = [
    '0x108', '0x118', '0x129', '0x132', '0x186', '0x1d5', '0x1d8', '0x201', '0x20c', '0x229', '0x238',
    '0x243', '0x249', '0x257', '0x25a', '0x261', '0x266', '0x273', '0x282', '0x292', '0x293', '0x2a7',
    '0x2b3', '0x2d3', '0x2e1', '0x2e5', '0x2f1', '0x2f3', '0x312', '0x315', '0x318', '0x321', '0x32c',
    '0x332', '0x334', '0x33a', '0x352', '0x353', '0x373', '0x376', '0x383', '0x39d', '0x3b6', '0x3d2',
    '0x3d8', '0x3e2', '0x3e3', '0x3f2', '0x3f5', '0x3fd', '0x401', '0x4f', '0x528', '0x7aa', '0x7ff',
    '0x2d2', '0x3b2', '0x3f2', '0x782'
]

mux_address = {
    '0x282': 2, '0x352': 2, '0x3fd': 3, '0x332': 2, '0x261': 2, '0x243': 3, '0x7ff': 8, '0x2e1': 3,
    '0x201': 3, '0x7aa': 4, '0x2b3': 4, '0x3f2': 4, '0x32c': 8, '0x401': 8, '0x3b2': 7, '0x782': 7
}

command = {
    'empty': bytes.fromhex('2955000000000000'),
    'volume_down': bytes.fromhex('2955010000000000'),
    'volume_up': bytes.fromhex('29553f0000000000'),
    'speed_down': bytes.fromhex('2955003f00000000'),
    'speed_up': bytes.fromhex('2955000100000000'),
    'distance_far': bytes.fromhex('2956000000000000'),
    'distance_near': bytes.fromhex('2959000000000000'),
    'door_open_fl': bytes.fromhex('6000000000000000'),
    'door_open_fr': bytes.fromhex('0003000000000000'),
    'door_open_rl': bytes.fromhex('0018000000000000'),
    'door_open_rr': bytes.fromhex('00c0000000000000'),
}

monitoring_addrs = {
    0x102: 'VCLEFT_doorStatus',
    0x103: 'VCRIGHT_doorStatus',
    0x108: 'DIR_torque',
    0x118: 'DriveSystemStatus',
    0x186: 'DIF_torque',
    0x257: 'DIspeed',
    0x261: '12vBattStatus',
    0x273: 'UI_vehicleControl',
    0x292: 'BMS_SOC',
    0x2f3: 'UI_hvacRequest',
    0x312: 'BMSthermal',
    0x33a: 'UI_rangeSOC',
    0x334: 'UI_powertrainControl',
    0x352: 'BMS_energyStatus',
    0x3c2: 'VCLEFT_switchStatus',
    0x31a: 'VCRIGHT_switchStatus',
    0x3f5: 'VCFRONT_lighting',
    0x39d: 'IBST_status',
    0x528: 'UnixTime',
    0x2d2: 'BMS_driveLimits',
    0x332: 'BMS_bmbMinMax',
    0x3b2: 'BMS_log2',
    0x3d2: 'BMS_kwhCounter',
    0x3f2: 'BMS_kwhCountersMultiplexed',
    0x401: 'BMS_brickMeasurements',
    0x782: 'BMS_log3',
}
