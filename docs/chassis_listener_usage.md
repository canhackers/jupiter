# Chassis Listener 사용법

`chassis_listener.py`는 **읽기 전용(Read-Only)** 으로 Chassis CAN 메시지를 수집하고, CSV로 내보내는 도구입니다.

---

## 1. 목적
- Chassis CAN 메시지를 수집(수신 전용)
- 시간당 메시지 개수 집계
- 주소별 상세 CSV 저장
- `Ctrl+C` 또는 안전 종료 신호에서도 중단 시점까지 저장

---

## 2. 기본 사양
- 채널: `can0` (기본)
- 기본 수집 시간: `600초` (10분)
- 기본 저장 경로: `/home/chassis_record`
- 기본 DBC 경로: `/home/jupiter/dbc/chassis_only.dbc`

---

## 3. 준비사항

### 3.1 Python 패키지
필수:
- `python-can`

선택(신호 decode 필요 시):
- `cantools`

예시:
```bash
pip install python-can
pip install cantools
```

> `cantools`가 없어도 수집/CSV 저장은 동작하며, `signal_json` 컬럼만 비어있게 됩니다.

### 3.2 DBC 파일
- ChassisBus만 포함된 고정 DBC 파일을 아래 경로에 준비:
  - `/home/jupiter/dbc/chassis_only.dbc`

다른 경로를 쓰려면 `--dbc` 옵션을 사용하세요.

---

## 4. 실행 방법

### 4.1 기본 실행 (권장)
```bash
python chassis_listener.py
```

### 4.2 실행 옵션 포함
```bash
python chassis_listener.py \
  --channel can0 \
  --duration 600 \
  --out /home/chassis_record \
  --dbc /home/jupiter/dbc/chassis_only.dbc
```

### 4.3 도움말
```bash
python chassis_listener.py --help
```

---

## 5. 안전 중단 방법

### 5.1 Ctrl + C 중단
실행 중 `Ctrl+C`를 누르면:
1. 수집 루프 종료
2. CSV export 실행
3. 중단 시점까지 데이터 저장 완료

### 5.2 stop-file 방식 중단 (원격/자동화용)
실행 시:
```bash
python chassis_listener.py --stop-file /tmp/chassis.stop
```

중단할 때:
```bash
touch /tmp/chassis.stop
```

`chassis_listener.py`가 파일 생성을 감지하면 정상 종료 + 저장합니다.

---

## 6. 출력 파일

기본 출력 디렉토리: `/home/chassis_record`

### 6.1 `hourly_summary.csv`
- 컬럼:
  - `hour_bucket`
  - `can_id_hex`
  - `message_count`

### 6.2 `addr_summary.csv`
- 컬럼:
  - `can_id_hex`
  - `message_name`
  - `total_count`
  - `first_seen`
  - `last_seen`
  - `dlc_set`

### 6.3 `addr_0xXXX.csv`
주소별 상세 파일
- 컬럼:
  - `ts_unix`
  - `ts_local`
  - `can_id_hex`
  - `message_name`
  - `dlc`
  - `data_hex`
  - `signal_names`
  - `signal_json`

---

## 7. 로그 예시
실행 시 콘솔에서 다음과 같은 상태 로그를 볼 수 있습니다.
- 시작 정보: 채널/시간/출력경로
- DBC 로드 결과: 대상 주소 수, 샘플 ID
- 주기 상태: 누적 수신 개수
- 종료 저장: CSV export 완료 메시지

---

## 8. 트러블슈팅

### 8.1 `python-can module is required` 오류
- 원인: `python-can` 미설치
- 해결:
```bash
pip install python-can
```

### 8.2 `DBC file not found` 오류
- 원인: 지정된 DBC 경로에 파일 없음
- 해결:
  - 파일 경로 확인
  - `--dbc`로 올바른 경로 전달

### 8.3 `cantools decode disabled` 출력
- 원인: `cantools` 미설치 또는 DBC decode 불가
- 영향: 수집/CSV 저장은 정상, `signal_json`만 비어 있을 수 있음
- 해결(선택):
```bash
pip install cantools
```

---

## 9. 운영 권장
- 첫 테스트는 3~5분으로 짧게 실행 후 CSV 구조 확인
- 이후 기본값(10분)으로 수집
- 파일 크기 증가 추이를 보고 필요 시 샘플링/로테이션 정책 추가
