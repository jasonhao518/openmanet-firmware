#!/usr/bin/env bash

set -euo pipefail

readonly firmware_name="HT-H7608-20250924.bin"
readonly firmware_url="https://resource.heltec.cn/download/HT-H7608/firmware/${firmware_name}"
readonly firmware_sha256="e4e2da99ce3eab85fdf58a7dfbdcf81f9e561411377151bba96be36e5c1daf02"
readonly firmware_size="27788086"
readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly kermit_script="${script_dir}/recover-stock.kermit"

port=""
firmware="${HOME}/Downloads/${firmware_name}"
assume_yes=0

usage() {
	cat <<'EOF'
Usage: recover-stock-macos.sh [--port DEVICE] [--firmware FILE] [--yes]

Recover a Heltec HT-H7608 V1 with the official 2025-09-24 stock firmware
through the U-Boot serial recovery menu.

Options:
  --port DEVICE    Serial port, for example /dev/cu.usbserial-BG0107WG
  --firmware FILE  Use an existing copy of the pinned official V1 image
  --yes            Skip the typed model confirmation
  -h, --help       Show this help

The script downloads the pinned image when it is absent. It refuses images
whose size or SHA-256 differs, including all HT-H7608 V2 images.
EOF
}

die() {
	printf 'Error: %s\n' "$*" >&2
	exit 1
}

while (($#)); do
	case "$1" in
		--port)
			(($# >= 2)) || die "--port requires a device path"
			port="$2"
			shift 2
			;;
		--firmware)
			(($# >= 2)) || die "--firmware requires a file path"
			firmware="$2"
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
		*)
			die "unknown argument: $1"
			;;
	esac
done

command -v kermit >/dev/null 2>&1 || die "OpenKermit is required: brew install openkermit"
command -v shasum >/dev/null 2>&1 || die "shasum is required"

if [[ ! -f "$firmware" ]]; then
	command -v curl >/dev/null 2>&1 || die "curl is required to download the firmware"
	printf 'Downloading official HT-H7608 V1 firmware to %s\n' "$firmware"
	mkdir -p "$(dirname "$firmware")"
	curl -fL --retry 3 --output "${firmware}.part" "$firmware_url"
	mv "${firmware}.part" "$firmware"
fi

actual_size="$(stat -f '%z' "$firmware" 2>/dev/null || stat -c '%s' "$firmware")"
[[ "$actual_size" == "$firmware_size" ]] ||
	die "firmware size is ${actual_size}, expected ${firmware_size}; refusing to flash"

actual_sha256="$(shasum -a 256 "$firmware" | awk '{print $1}')"
[[ "$actual_sha256" == "$firmware_sha256" ]] ||
	die "firmware SHA-256 does not match the pinned HT-H7608 V1 stock image"

magic="$(od -An -tx1 -N4 "$firmware" | tr -d ' \n')"
[[ "$magic" == "27051956" ]] || die "firmware does not have a U-Boot legacy-image header"

if [[ -z "$port" ]]; then
	shopt -s nullglob
	serial_ports=(/dev/cu.usbserial-* /dev/cu.usbmodem*)
	shopt -u nullglob

	case "${#serial_ports[@]}" in
		0) die "no USB serial adapter found under /dev/cu.usbserial-* or /dev/cu.usbmodem*" ;;
		1) port="${serial_ports[0]}" ;;
		*)
			printf 'Detected more than one serial device:\n' >&2
			printf '  %s\n' "${serial_ports[@]}" >&2
			die "select one with --port DEVICE"
			;;
	esac
fi

[[ -c "$port" ]] || die "serial port is not a character device: $port"
[[ "$port" != *[[:space:]]* ]] || die "serial-port paths containing whitespace are not supported"
[[ "$firmware" != *[[:space:]]* ]] || die "firmware paths containing whitespace are not supported"

printf '\nHeltec HT-H7608 V1 serial recovery\n'
printf '  Port:     %s\n' "$port"
printf '  Firmware: %s\n' "$firmware"
printf '  SHA-256:  %s\n\n' "$actual_sha256"
printf '%s\n' 'This erases and rewrites only the Linux firmware partition.'
printf '%s\n' 'It does not overwrite U-Boot, the U-Boot environment, or factory calibration.'
printf '%s\n\n' 'Keep stable power connected for the entire transfer and flash operation.'

if ((assume_yes == 0)); then
	read -r -p 'Type RECOVER-V1 to continue: ' confirmation
	[[ "$confirmation" == "RECOVER-V1" ]] || die "confirmation did not match"
fi

printf '\nStarting recovery. Power-cycle the HT-H7608 when prompted.\n\n'
exec kermit "$kermit_script" -Y = "$port" "$firmware"
