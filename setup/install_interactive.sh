#!/usr/bin/env bash

set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

mkdir -p "${STATE_DIR}"

STEP_LOG="${STATE_DIR}/install-last-step.log"
INSTALL_LOG="${STATE_DIR}/install.log"
REBOOT_MARKER="${STATE_DIR}/reboot-required"

step_prompt() {
    local step_no="$1"
    local title="$2"
    local description="$3"

    printf '\n============================================================\n'
    printf '%s단계: %s\n' "${step_no}" "${title}"
    printf '%s\n' "${description}"
    read -r -p "진행할까요? 계속하려면 Y를 입력하세요: " answer
    case "${answer}" in
        Y|y) ;;
        *) printf '\n설치를 중단했습니다. 다시 시작하려면 bash setup/install_interactive.sh 를 실행하세요.\n'; exit 0 ;;
    esac
}

last_failure_reason() {
    if [[ -s "${STEP_LOG}" ]]; then
        grep -E '\[ERROR\]|\[WARN\]|error|Error|failed|Failed|실패|없습니다|찾지 못했습니다' "${STEP_LOG}" | tail -n 1 | sed 's/^[[:space:]]*//' || true
    fi
}

run_step() {
    local step_no="$1"
    local title="$2"
    local description="$3"
    local function_name="$4"

    step_prompt "${step_no}" "${title}" "${description}"
    printf '\n%s단계 진행 중입니다...\n' "${step_no}"
    : >"${STEP_LOG}"
    printf '\n[%s] %s단계 시작: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${step_no}" "${title}" >>"${INSTALL_LOG}"

    set +e
    "${function_name}" 2>&1 | tee "${STEP_LOG}" | tee -a "${INSTALL_LOG}"
    local status=${PIPESTATUS[0]}
    set -e

    if [[ "${status}" -eq 0 ]]; then
        printf '\n%s단계 진행 결과 성공입니다.\n' "${step_no}"
        printf '[%s] %s단계 성공: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${step_no}" "${title}" >>"${INSTALL_LOG}"
    else
        local reason
        reason="$(last_failure_reason)"
        [[ -n "${reason}" ]] || reason="자세한 원인은 ${STEP_LOG} 로그를 확인해야 합니다."
        printf '\n%s단계 진행 결과 실패입니다.\n' "${step_no}"
        printf '실패 사유는 %s 입니다.\n' "${reason}"
        printf '[%s] %s단계 실패: %s / %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${step_no}" "${title}" "${reason}" >>"${INSTALL_LOG}"
        printf '\n전체 설치 로그: %s\n' "${INSTALL_LOG}"
        exit "${status}"
    fi
}

yes_no() {
    local question="$1"
    read -r -p "${question} [Y/n]: " answer
    case "${answer}" in
        ''|Y|y) return 0 ;;
        *) return 1 ;;
    esac
}

check_project_files() {
    info "프로젝트 경로: ${PROJECT_DIR}"
    if [[ "${PROJECT_DIR}" != "${EXPECTED_PROJECT_DIR}" ]]; then
        warn "권장 경로는 ${EXPECTED_PROJECT_DIR} 입니다. 현재 경로로도 설치는 계속할 수 있습니다."
    fi

    if [[ "$(id -u)" -eq 0 ]]; then
        warn "root 사용자로 실행 중입니다. 일반 사용자(zero)로 실행하고 필요한 순간에만 sudo를 쓰는 것을 권장합니다."
    fi

    require_project_file "jupiter.py"
    require_project_file "settings.py"
    require_project_file "can_io.py"
    require_project_file "feature_stack.py"
    require_project_file "features"
    require_project_file "setup"
    require_project_file "jupiter_slim_case.stl"

    require_command python3
    python3 --version

    if is_raspberry_pi; then
        info "Raspberry Pi 환경으로 보입니다: $(tr -d '\0' </proc/device-tree/model)"
    else
        warn "Raspberry Pi로 확인되지 않았습니다. PC 검토 환경이면 정상이고, 실제 설치는 Pi에서 실행하세요."
    fi
}

install_system_packages() {
    require_sudo

    local missing=()
    for command_name in git python3 ifconfig ip; do
        if ! command -v "${command_name}" >/dev/null 2>&1; then
            missing+=("${command_name}")
        fi
    done
    if ! python3 -m venv --help >/dev/null 2>&1; then
        missing+=("python3-venv")
    fi
    if ! command -v candump >/dev/null 2>&1; then
        missing+=("can-utils")
    fi

    if [[ "${#missing[@]}" -eq 0 ]]; then
        info "필수 시스템 패키지가 이미 준비되어 있습니다."
    else
        info "부족한 항목이 있어 apt 설치를 진행합니다: ${missing[*]}"
        run sudo apt-get update
        run sudo apt-get install -y git python3-venv python3-pip net-tools iproute2 can-utils
    fi

    require_command git
    require_command ifconfig
    require_command ip
    require_command candump
    python3 -m venv --help >/dev/null
}

install_python_environment() {
    require_command python3

    if [[ ! -d "${VENV_DIR}" ]]; then
        run python3 -m venv "${VENV_DIR}"
    else
        info "기존 가상환경을 사용합니다: ${VENV_DIR}"
    fi

    [[ -x "${PYTHON_BIN}" ]] || die "가상환경 Python을 찾지 못했습니다: ${PYTHON_BIN}"

    run "${PYTHON_BIN}" -m pip install --upgrade pip
    run "${PIP_BIN}" install python-can vcgencmd bleak

    "${PYTHON_BIN}" - <<'PY'
import can
from vcgencmd import Vcgencmd
import bleak

print("Python 의존성 import 확인 완료")
PY
}

configure_can_boot() {
    require_sudo

    local boot_config
    boot_config="$(find_boot_config)" || die "Raspberry Pi 부팅 설정 파일을 찾지 못했습니다."
    info "부팅 설정 파일: ${boot_config}"

    local backup_path="${boot_config}.jupiter-backup.$(date +%Y%m%d-%H%M%S)"
    run sudo cp -a "${boot_config}" "${backup_path}"
    info "백업 생성: ${backup_path}"

    local changed=0
    local required_lines=(
        "dtparam=spi=on"
        "dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000"
    )

    for line in "${required_lines[@]}"; do
        if sudo grep -Fxq "${line}" "${boot_config}"; then
            info "이미 존재함: ${line}"
        else
            printf '%s\n' "${line}" | sudo tee -a "${boot_config}" >/dev/null
            info "추가함: ${line}"
            changed=1
        fi
    done

    for line in "${required_lines[@]}"; do
        sudo grep -Fxq "${line}" "${boot_config}" || die "설정 검증 실패: ${line}"
    done

    if [[ "${changed}" -eq 1 ]]; then
        touch "${REBOOT_MARKER}"
        warn "CAN HAT 부팅 설정이 새로 추가되었습니다. can0 확인과 smoke test 전에 재부팅이 필요합니다."
    else
        info "CAN HAT 부팅 설정은 이미 들어 있습니다."
    fi
}

maybe_reboot_after_boot_config() {
    if [[ -f "${REBOOT_MARKER}" ]] && ! ip link show can0 >/dev/null 2>&1; then
        printf '\nCAN 설정 반영에는 재부팅이 필요합니다.\n'
        printf '재부팅 후 다시 아래 명령을 실행하면 설치기가 앞 단계는 확인만 하고 이어서 진행합니다.\n'
        printf '  cd %s && bash setup/install_interactive.sh\n' "${PROJECT_DIR}"
        if yes_no "지금 재부팅할까요?"; then
            require_sudo
            run sudo reboot
        fi
        printf '\n재부팅 전에는 smoke test와 서비스 등록을 안전하게 계속할 수 없어 여기서 멈춥니다.\n'
        exit 0
    fi
}

run_smoke_test() {
    [[ -x "${PYTHON_BIN}" ]] || die "가상환경 Python이 없습니다. 먼저 Python 환경설정이 필요합니다: ${PYTHON_BIN}"

    mapfile -d '' python_files < <(
        find "${PROJECT_DIR}" \
            -path "${VENV_DIR}" -prune -o \
            -path "${PROJECT_DIR}/.git" -prune -o \
            -path "${PROJECT_DIR}/.setup" -prune -o \
            -path "${PROJECT_DIR}/.pytest_cache" -prune -o \
            -path "${PROJECT_DIR}/__pycache__" -prune -o \
            -name '*.py' -print0
    )

    if [[ "${#python_files[@]}" -gt 0 ]]; then
        run "${PYTHON_BIN}" -m py_compile "${python_files[@]}"
    fi

    "${PYTHON_BIN}" - <<'PY'
import can
from vcgencmd import Vcgencmd
import jupiter
import feature_stack
import state
import runtime

print("core module import 확인 완료")
PY

    if [[ -d "${PROJECT_DIR}/tests" ]]; then
        run "${PYTHON_BIN}" -m unittest discover -s "${PROJECT_DIR}/tests"
    else
        warn "tests 폴더가 없어 단위 테스트는 건너뜁니다."
    fi

    if ip link show can0 >/dev/null 2>&1; then
        ip -details link show can0
        info "can0 인터페이스 확인 완료"
        rm -f "${REBOOT_MARKER}"
    else
        die "can0 인터페이스가 없습니다. CAN HAT 설정 후 재부팅했는지, HAT 연결 상태와 config.txt를 확인하세요."
    fi
}

render_service_file() {
    cat <<EOF
[Unit]
Description=Jupiter CAN runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PYTHON_BIN} ${PROJECT_DIR}/jupiter.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
}

install_autostart_service() {
    require_sudo
    [[ -x "${PYTHON_BIN}" ]] || die "가상환경 Python이 없습니다: ${PYTHON_BIN}"
    require_project_file "setup/jupiter.sh"

    local service_path="/etc/systemd/system/${SERVICE_NAME}"
    local jupiter_command_path="/usr/local/bin/jupiter.sh"
    local temp_service
    temp_service="$(mktemp)"
    render_service_file >"${temp_service}"

    if [[ -f "${service_path}" ]]; then
        if sudo cmp -s "${temp_service}" "${service_path}"; then
            info "${SERVICE_NAME} 서비스는 이미 같은 내용으로 등록되어 있습니다. 중복 등록하지 않습니다."
        else
            warn "기존 ${service_path} 파일이 현재 설치 내용과 다릅니다."
            if yes_no "기존 서비스 파일을 백업하고 새 내용으로 교체할까요?"; then
                run sudo cp -a "${service_path}" "${service_path}.jupiter-backup.$(date +%Y%m%d-%H%M%S)"
                run sudo install -m 0644 "${temp_service}" "${service_path}"
            else
                rm -f "${temp_service}"
                die "서비스 파일 교체를 사용자가 거부했습니다."
            fi
        fi
    else
        run sudo install -m 0644 "${temp_service}" "${service_path}"
    fi

    rm -f "${temp_service}"
    run sudo systemctl daemon-reload
    run sudo systemctl enable "${SERVICE_NAME}"
    run sudo install -m 0755 "${PROJECT_DIR}/setup/jupiter.sh" "${jupiter_command_path}"
    sudo systemctl is-enabled "${SERVICE_NAME}" >/dev/null
    sudo systemctl cat "${SERVICE_NAME}" >/dev/null
    [[ -x "${jupiter_command_path}" ]] || die "jupiter.sh 설치 검증에 실패했습니다: ${jupiter_command_path}"
}

manual_start_prompt() {
    printf '\n자동 실행 서비스 등록까지 완료했습니다.\n'
    printf '재부팅하면 %s 서비스가 자동으로 시작됩니다.\n' "${SERVICE_NAME}"
    if yes_no "재부팅 전 지금 직접 서비스를 실행해볼까요?"; then
        require_sudo
        if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
            if yes_no "서비스가 이미 실행 중입니다. 재시작해볼까요?"; then
                run sudo systemctl restart "${SERVICE_NAME}"
            else
                info "이미 실행 중인 서비스를 그대로 둡니다."
            fi
        else
            run sudo systemctl start "${SERVICE_NAME}"
        fi
        sleep 3
        if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
            info "${SERVICE_NAME} 서비스가 active 상태입니다."
            sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true
            printf '\n실행/모니터링 세션에 들어가려면 다음 명령을 사용하세요.\n'
            printf '  jupiter.sh\n'
        else
            warn "${SERVICE_NAME} 서비스가 active 상태가 아닙니다. 최근 로그를 출력합니다."
            sudo journalctl -u "${SERVICE_NAME}" -n 120 --no-pager || true
            die "서비스 수동 실행 검증에 실패했습니다."
        fi
    else
        info "수동 실행은 건너뜁니다. 다음 재부팅 때 서비스가 자동 시작됩니다."
    fi
}

main() {
    printf '\nJupiter 대화형 설치기\n'
    printf '모든 단계는 설명 후 Y 확인을 받아 진행하고, 성공/실패와 실패 사유를 출력합니다.\n'
    printf '설치 로그: %s\n' "${INSTALL_LOG}"

    run_step "1" "환경설정 기본 확인" "프로젝트 위치, 필수 파일, Python, Raspberry Pi 여부를 확인합니다. 시스템 설정은 변경하지 않습니다." check_project_files
    run_step "2" "시스템 패키지 설치" "git, python3-venv, python3-pip, net-tools, iproute2, can-utils를 준비합니다." install_system_packages
    run_step "3" "Python 실행환경 구성" ".venv 가상환경을 만들고 python-can, vcgencmd, bleak 의존성을 설치합니다." install_python_environment
    run_step "4" "CAN HAT 부팅 설정" "config.txt를 백업하고 MCP2515 CAN HAT overlay 설정을 중복 없이 추가합니다." configure_can_boot
    maybe_reboot_after_boot_config
    run_step "5" "Smoke Test" "Python 문법, core import, 단위 테스트, can0 인터페이스 존재를 한 번에 검증합니다. CAN 메시지는 송신하지 않습니다." run_smoke_test
    run_step "6" "자동 실행 서비스 등록" "모든 smoke test가 성공했을 때 systemd 서비스를 등록합니다. 기존 등록이 있으면 중복 등록하지 않습니다." install_autostart_service
    manual_start_prompt

    printf '\n설치 절차가 완료되었습니다.\n'
    printf '실행/모니터링: jupiter.sh\n'
    printf '재부팅: sudo reboot\n'
}

main "$@"
