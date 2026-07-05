import json
import os


json_file = os.path.join('/home/jupiter_settings.json')


DEFAULT_SETTINGS = {
    'Logger': 1,
    'RearCenterBuckle': 1,
    'MapLampLeftShort': None,
    'MapLampLeftLong': 'mirror_fold',
    'MapLampLeftDouble': None,
    'MapLampRightShort': None,
    'MapLampRightLong': 'open_door_rr,buckle_emulator',    # 두개의 함수가 선언되는 경우는 주차 중, 주행 중 기능
    'MapLampRightDouble': 'open_door_fr,mars_mode_toggle',
    'AutoRecirculation': 1,
    'KickDown': 1,
    'MarsMode': 0,
    'KeepWiperSpeed': 1,
    'SlowWiper': 1,
    'AltTurnSignal': 1,
    'AutoFollowingDistance': 1,
    'MirrorAutoFold': 0,
    'NavdyHud': 0
}


def load_settings(path=json_file):
    default_settings = DEFAULT_SETTINGS.copy()
    if not os.path.exists(path):
        # 설정 파일이 없으면 기본 설정 파일 생성
        with open(path, 'w') as f:
            json.dump(default_settings, f, indent=4)
        print(f"기본 설정 파일을 생성했습니다: {path}")
        return default_settings

    try:
        with open(path, 'r') as f:
            settings = json.load(f)
            for key, val in settings.items():
                print(f'{key} : [{val}]')
                default_settings[key] = val
        with open(path, 'w') as f:
            json.dump(default_settings, f, indent=4)
        return default_settings
    except:
        error_file = path.split('.')[0] + '_error.json'
        os.rename(path, error_file)
        with open(path, 'w') as f:
            json.dump(default_settings, f, indent=4)
        print(f"파일 양식에 오류가 있어 기본 설정 파일을 재생성했습니다.\n기존 파일은 settings_error.json으로 변경됩니다.")
        return default_settings
