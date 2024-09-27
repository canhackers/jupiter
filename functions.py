import os
import json

json_file = os.path.join('/home/jupiter_settings.json')
def initialize_canbus_connection():
    try:
        os.system('sudo modprobe -r mcp251x')
        os.system('sudo modprobe mcp251x')
        os.system('sudo ip link set can0 type can bitrate 500000')
        os.system('sudo ifconfig can0 down')
        os.system('sudo ifconfig can0 up')
        print('can bus initialized')
        return True
    except Exception as e:
        print('CAN Bus Initialize Error', e)
        return False

def load_settings():
    default_settings = {
        'Logger': 1,
        'RearCenterBuckle': 1,
        'MapLampLeftLong' : 'mirror_fold',
        'MapLampRightLong' : 'open_door_rr,buckle_emulator',    # 두개의 함수가 선언되는 경우는 주차 중, 주행 중 기능
        'MapLampRightDouble': 'open_door_fr,mars_mode_toggle',
        'AutoRecirculation' : 1,
        'KickDown' : 1,
        'KeepWiperSpeed': 1,
        'SlowWiper' : 1,
        'AltTurnSignal' : 1,
        'AutoFollowingDistance' : 1,
        'MirrorAutoFold' : 0,
        'NavdyHud' : 0
    }
    if not os.path.exists(json_file):
        # 설정 파일이 없으면 기본 설정 파일 생성
        with open(json_file, 'w') as f:
            json.dump(default_settings, f, indent=4)
        print(f"기본 설정 파일을 생성했습니다: {json_file}")
        return default_settings

    try:
        with open(json_file, 'r') as f:
            settings = json.load(f)
            for key, val in settings.items():
                print(f'{key} : [{val}]')
                default_settings[key] = val
        with open(json_file, 'w') as f:
            json.dump(default_settings, f, indent=4)
        return settings
    except:
        error_file = json_file.split('.')[0] + '_error.json'
        os.rename(json_file, error_file)
        with open(json_file, 'w') as f:
            json.dump(default_settings, f, indent=4)
        print(f"파일 양식에 오류가 있어 기본 설정 파일을 재생성했습니다.\n기존 파일은 settings_error.json으로 변경됩니다.")
        return default_settings