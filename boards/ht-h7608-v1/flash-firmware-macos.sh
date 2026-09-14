#!/usr/bin/env bash

set -euo pipefail

readonly max_firmware_size=33226752
readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly kermit_script="${script_dir}/flash-firmware.kermit"

port=""
firmware=""
expected_sha256=""
assume_yes=0

usage() {
	cat <<'EOF'
Usage: flash-firmware-macos.sh --firmware FILE [options]

Flash an HT-H7608 V1 Linux factory/system image through U-Boot option 0.

Options:
  --firmware FILE   U-Boot legacy factory/system image to flash (required)
  --sha256 HASH     Require this SHA-256 before flashing (recommended)
  --port DEVICE     Serial port, e.g. /dev/cu.usbserial-BG0107WG
  --yes             Skip the typed model confirmation
  -h, --help        Show this help

This script never selects U-Boot options 7 or 9 and never writes the
bootloader, environment, or factory-calibration partitions.
EOF
}

die() {
	printf 'Error: %s\n' "$*" >&2
	exit 1
}

while (($#)); do
	case "$1" in
		--firmware)
			(($# >= 2)) || die "--firmware requires a file path"
			firmware="$2"
			shift 2
			;;
		--sha256)
			(($# >= 2)) || die "--sha256 requires a hash"
			expected_sha256="$2"
			shift 2
			;;
		--port)
			(($# >= 2)) || die "--port requires a device path"
			port="$2"
			shift 2
			;;
		--yes)
			assume_yes=1
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*) die "unknown argument: $1" ;;
	esac
done

[[ -n "$firmware" ]] || die "--firmware is required"
[[ -f "$firmware" ]] || die "firmware file not found: $firmware"
command -v kermit >/dev/null 2>&1 || die "OpenKermit is required: brew install openkermit"
command -v shasum >/dev/null 2>&1 || die "shasum is required"

actual_size="$(stat -f '%z' "$firmware" 2>/dev/null || stat -c '%s' "$firmware")"
((actual_size > 64)) || die "firmware is too small"
((actual_size <= max_firmware_size)) || die "firmware exceeds the 0x1fb0000-byte V1 firmware partition"

magic="$(od -An -tx1 -N4 "$firmware" | tr -d ' \n')"
[[ "$magic" == "27051956" ]] || die "firmware does not have a U-Boot legacy-image header"

actual_sha256="$(shasum -a 256 "$firmware" | awk '{print $1}')"
if [[ -n "$expected_sha256" ]]; then
	[[ "$expected_sha256" =~ ^[[:xdigit:]]{64}$ ]] || die "--sha256 must contain 64 hexadecimal characters"
	normalized_expected_sha256="$(printf '%s' "$expected_sha256" | tr '[:upper:]' '[:lower:]')"
	[[ "$actual_sha256" == "$normalized_expected_sha256" ]] || die "firmware SHA-256 does not match --sha256"
fi

if [[ -z "$port" ]]; then
	shopt -s nullglob
	serial_ports=(/dev/cu.usbserial-* /dev/cu.usbmodem*)
	shopt -u nullglob
	case "${#serial_ports[@]}" in
		0) die "no USB serial adapter found" ;;
		1) port="${serial_ports[0]}" ;;
		*) printf 'Detected serial devices:\n  %s\n' "${serial_ports[@]}" >&2; die "select one with --port" ;;
	esac
fi

[[ -c "$port" ]] || die "serial port is not a character device: $port"
[[ "$port" != *[[:space:]]* ]] || die "serial-port paths containing whitespace are unsupported"
[[ "$firmware" != *[[:space:]]* ]] || die "firmware paths containing whitespace are unsupported"

printf '\nHT-H7608 V1 system firmware flash\n'
printf '  Port:     %s\n' "$port"
printf '  Firmware: %s\n' "$firmware"
printf '  Size:     %s bytes\n' "$actual_size"
printf '  SHA-256:  %s\n\n' "$actual_sha256"
printf '%s\n' 'Stable power is required throughout transfer and programming.'
printf '%s\n\n' 'Only the Linux firmware partition will be rewritten.'

if ((assume_yes == 0)); then
	read -r -p 'Type FLASH-H7608-V1 to continue: ' confirmation
	[[ "$confirmation" == "FLASH-H7608-V1" ]] || die "confirmation did not match"
fi

printf '\nStarting. Power-cycle the HT-H7608 when prompted.\n\n'
exec kermit "$kermit_script" -Y = "$port" "$firmware"
