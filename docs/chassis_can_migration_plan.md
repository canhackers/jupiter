# Chassis CAN 읽기 전용 도구 구축 계획 (1차)

## 1) 목표 및 전제
- 기존 `jupiter.py`의 **Vehicle CAN 변조/송신 중심 구조**와 분리하여, Chassis CAN 전용으로 **읽기 전용(sniffer)** 도구를 신규 구성한다.
- 이번 1차 단계는 기능 구현 전, 구조/흐름/산출물 중심의 계획 확정이 목적이다.
- 요구사항 핵심:
  1. 기능 요소 클래스(Autopilot, KickDown, ButtonManager 등) 제거
  2. ChassisBus 메시지 수신 누적
  3. 시간당 메시지 개수 집계
  4. 주소별 분석 가능한 형태의 CSV export
  5. DBC는 `Model3CAN.dbc`의 ChassisBus 기준 사용

---

## 2) 브랜치 전략
- 신규 작업 브랜치: `feat/chassis-can-listener-plan`
- 이후 구현 브랜치는 동일 prefix 사용 권장
  - 예: `feat/chassis-can-listener-core`, `feat/chassis-can-listener-csv`

---

## 3) 리팩토링 최소화 원칙 (기존 스타일 유지)
- 기존 프로젝트의 패턴(단일 루프 + 클래스 단위 책임 분리 + 명시적 if 분기)을 유지한다.
- 대규모 구조 변경(패키지 전면 재구성, 추상화 과도 도입)은 하지 않는다.
- 신규 파일 추가 위주로 진행하고, 기존 `jupiter.py`/`tesla.py`는 가급적 건드리지 않거나 최소 수정한다.

---

## 4) 1차 구현 대상 아키텍처

### 4.1 엔트리 포인트
- 신규 실행 파일 제안: `chassis_listener.py`
- 역할:
  - CAN 인터페이스 초기화 (`functions.initialize_canbus_connection` 재사용 가능)
  - 읽기 루프 실행
  - 주기적 집계 flush
  - 종료 시점 CSV 저장

### 4.2 핵심 클래스 제안
1. `ChassisMonitor`
   - 입력: 수신 CAN 프레임 (`arbitration_id`, `data`, `timestamp`)
   - 기능:
     - ChassisBus 대상 주소 필터링
     - 주소별 카운트 누적
     - 주소+payload 패턴(또는 mux) 단위 샘플 저장

2. `HourlyStats`
   - 기능:
     - 1시간 버킷(`YYYY-mm-dd HH:00:00`) 단위 카운트 집계
     - 주소별 시간당 개수 집계

3. `ChassisCsvExporter`
   - 기능:
     - CSV 다중 파일 출력
     - 파일 분리 방식:
       - `hourly_summary.csv` (시간당 총량/주소별량)
       - `addr_summary.csv` (주소별 총 수신량, 첫/마지막 수신시각)
       - `addr_<hexid>.csv` (주소별 상세 raw/해석 가능 형태)

### 4.3 저장 형식(초안)
- 공통 시간 포맷: unix + local datetime 병행
- `hourly_summary.csv`
  - `hour_bucket, can_id_hex, message_count`
- `addr_summary.csv`
  - `can_id_hex, total_count, first_seen, last_seen, dlc_set`
- `addr_<hexid>.csv`
  - `ts_unix, ts_local, can_id_hex, dlc, data_hex, mux, signal_json`

> `signal_json`은 DBC 해석 성공 시 key-value JSON 문자열, 실패 시 빈값.

---

## 5) DBC 연동 계획 (ChassisBus 주소 자동 추출)

### 5.1 수동 하드코딩 지양
- ChassisBus 주소 목록을 코드에 고정하지 않고, 시작 시 DBC에서 자동 추출.
- 이유:
  - DBC 업데이트 대응
  - 유지보수 비용 절감

### 5.2 파싱 방식
- 1순위: `cantools` 기반 로딩 후 message metadata에서 bus/channel 정보 확인
- 2순위(호환성 대비): DBC 원문 라인 파싱 fallback
  - `BO_` 정의 + bus 주석(`CM_`, `BA_`) 매핑

### 5.3 검증
- 시작 로그에 다음 출력:
  - `ChassisBus addr count`
  - 샘플 주소 목록(상위 20개)
- 주소가 0개일 경우 안전 중단(실수 방지)


### 5.4 파일 구조 실검토 결과 반영 (중요)
- `Model3CAN.dbc`는 노드 목록에 `BU_: Receiver ChassisBus VehicleBus PartyBus` 형태가 존재한다.
- 각 메시지는 `BO_ <decimal_id> <message_name>: <dlc> <sender_node>` 구조이며, 마지막 `<sender_node>`가 `VehicleBus`/`ChassisBus`/`PartyBus` 중 하나로 기록된다.
- 따라서 Chassis 대상 주소 추출은 **`BO_` 라인의 sender_node가 `ChassisBus`인지 판별**하면 안정적으로 동작한다.
- 주소 값은 DBC 원문상 10진수이므로, 내부 저장은 int로 유지하고 출력 시 `0x%03X` 포맷으로 병행 표기한다.
- 구현 시 `cantools`만 의존하지 않고, 위 규칙을 사용하는 경량 라인 파서를 기본 경로로 둔다(호환성/재현성 목적).

---

## 6) 읽기 전용 보장 설계
- 송신 관련 객체/버퍼/`can_bus.send()` 경로 제거
- 코드 레벨 가드:
  - `READ_ONLY = True` 상수
  - 송신 API 호출 흔적 존재 시 예외 발생
- 운영 가드:
  - CLI 옵션 기본값 `--no-send` 고정
  - 향후 확장에도 기본은 읽기 전용 유지

---

## 7) 실행/운영 시나리오

### 7.1 예시 CLI
- `python chassis_listener.py --channel can0 --duration 600 --out /home/chassis_record --dbc /home/jupiter/dbc/chassis_only.dbc`

### 7.2 동작
1. CAN 연결
2. DBC 로드 및 ChassisBus ID 세트 준비
3. 수신 루프(`recv(timeout=1)`)
4. 대상 ID면 누적
5. 1시간 버킷 집계 갱신
6. 종료 시 CSV export

### 7.3 종료 조건
- `--duration` 만료
- `Ctrl+C`
- 치명적 CAN 오류

### 7.4 수집 범위/중단 정책 (확정)
- 기본 채널은 **`can0` 고정** (현재 Zero 2W + 1채널 CAN HAT 전제).
- 주소별 상세 CSV는 **전체 기록**을 기본으로 하되, 기본 수집 시간은 **최대 10분(600초)** 으로 제한한다.
- 사용자가 `Ctrl+C`로 중단해도, 종료 시그널 핸들러에서 즉시 flush/export하여 **중단 시점까지 데이터 보존**을 보장한다.
- `Ctrl+C` 외 안전 종료 인터페이스도 제공한다.
  - 예: `--stop-file /tmp/chassis.stop` 지정 시, 파일 생성 감지 후 정상 종료+저장

---

## 8) 단계별 구현 로드맵

### Phase A (기초)
- `chassis_listener.py` 골격
- read-only 수신 루프
- 주소별 총 카운트

### Phase B (집계)
- 시간당 버킷 집계
- 주소별 first/last seen, dlc set

### Phase C (DBC 연동)
- ChassisBus 주소 자동 추출
- 신호 해석(`signal_json`) 지원

### Phase D (출력)
- CSV 3종 export
- 실행 요약 로그(총 메시지/주소 수/시간당 평균)

### Phase E (안정화)
- CAN 재연결 처리
- 대용량 수집 시 메모리 제한(샘플링/로테이션)

---

## 9) 리스크 및 대응
- DBC 내 ChassisBus 표기 방식이 버전별로 상이할 수 있음
  - 대응: 메타 파싱 + fallback 파싱 이중화
- 장시간 수집 시 주소별 raw 저장량 증가
  - 대응: per-address max rows 옵션, 또는 간격 샘플링
- 차량 SW 업데이트로 주소 세트 변경
  - 대응: 런타임 DBC 재적용, 결과물에 DBC 해시/버전 기록

---

## 10) 다음 액션 제안
1. `chassis_listener.py` 최소 동작 버전(Phase A) 구현 (`can0`, read-only, 600초 기본)
2. SIGINT(`Ctrl+C`) 및 stop-file 기반 안전 종료+저장 구현
3. 실제 차량 10분 이내 전체 기록 테스트 후 CSV 포맷 확정
4. 고정형 Chassis 전용 DBC 파일 기반 신호 해석(Phase C) 추가

---

## 11) 확정 사항 (요청 반영)
- 수집 채널명: **`can0` 고정** (1채널 CAN HAT 사용 중이므로 동시 2채널 미지원).
- 결과 저장 기본 경로: **`/home/chassis_record` 사용**.
- 주소별 상세 기록 정책: **전체 기록** 우선, 단 기본 런타임은 **최대 10분**.
- 중단 정책: `Ctrl+C` 시점까지 반드시 저장되도록 종료 핸들러 구현 + stop-file 기반 안전 종료 인터페이스 제공.
- DBC 공급 방식: **ChassisBus만 추출한 고정 DBC 파일**을 로컬 경로로 사용.

## 12) 추후 확장 포인트
- 하드웨어가 2채널 CAN 지원으로 변경되면 `--channel` 다중화(`can0`, `can1`) 옵션 추가 검토.
- 10분 이상 장시간 수집이 필요해지면 샘플링/로테이션 모드 추가.
