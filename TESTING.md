# 테스트 가이드

## PC에서 가능한 테스트

현재 리팩터링 브랜치는 외부 장치 없이 실행 가능한 단위 테스트를 포함합니다.

```powershell
python -m unittest discover -s tests
```

현재 테스트 범위:

- `packets.py`: bit field 읽기/쓰기, signed 값, counter/checksum 포함 패킷 생성
- `state.py`: `Dashboard.update()`의 주요 상태 갱신
- `features/`: 주요 `check(bus, address, byte_data)` payload 변조
- `feature_stack.py`: 설정값이 기능 객체와 버튼 매핑으로 연결되는지 확인
- `jupiter.py`: bus watchdog, feature dispatch, send buffer helper

## 컴파일 확인

문법 문제를 빠르게 확인하려면 아래 명령을 사용합니다.

```powershell
python -m compileall -q .
```

## 한계

- PC 테스트는 실제 `can0`, MCP251x, Raspberry Pi `vcgencmd`, Bluetooth 장치, 차량 CAN timing을 검증하지 않습니다.
- `jupiter.py` 런타임 helper 테스트는 `can`과 `vcgencmd`를 fake module로 대체합니다.
- 실차 전 확인에서는 `python -m unittest discover -s tests`가 통과하는지 먼저 보고, 이후 Raspberry Pi에서 import와 서비스 실행을 확인합니다.
