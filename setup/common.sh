#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"
SERVICE_NAME="jupiter.service"
EXPECTED_PROJECT_DIR="${EXPECTED_PROJECT_DIR:-/home/zero/jupiter}"
STATE_DIR="${PROJECT_DIR}/.setup"

info() {
    printf '\n[INFO] %s\n' "$*"
}

warn() {
    printf '\n[WARN] %s\n' "$*" >&2
}

die() {
    printf '\n[ERROR] %s\n' "$*" >&2
    exit 1
}

confirm_step() {
    local message="$1"
    printf '\n%s\n' "$message"
    read -r -p "계속하려면 Y를 입력하세요: " answer
    case "$answer" in
        Y|y) ;;
        *) info "사용자가 중단했습니다."; exit 0 ;;
    esac
}

require_command() {
    local command_name="$1"
    command -v "$command_name" >/dev/null 2>&1 || die "'${command_name}' 명령을 찾을 수 없습니다."
}

require_project_file() {
    local path="$1"
    [[ -e "${PROJECT_DIR}/${path}" ]] || die "필수 파일/폴더가 없습니다: ${PROJECT_DIR}/${path}"
}

require_sudo() {
    require_command sudo
    sudo -v
}

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    "$@"
}

is_raspberry_pi() {
    [[ -r /proc/device-tree/model ]] && tr -d '\0' </proc/device-tree/model | grep -qi 'raspberry pi'
}

find_boot_config() {
    if [[ -f /boot/firmware/config.txt ]]; then
        printf '%s\n' /boot/firmware/config.txt
    elif [[ -f /boot/config.txt ]]; then
        printf '%s\n' /boot/config.txt
    else
        return 1
    fi
}

print_next_step() {
    local next="$1"
    printf '\n[NEXT] 다음 단계: %s\n' "$next"
}
