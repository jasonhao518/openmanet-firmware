#!/bin/sh

. /lib/functions.sh

LOCK_DIR=/var/run/mt76x8-powersave.lock

load_settings() {
	config_load mt76x8-powersave
	config_get_bool enabled main enabled 1
	config_get idle_seconds main idle_seconds 300
	config_get poll_seconds main poll_seconds 5
	config_get traffic_threshold_bytes main traffic_threshold_bytes 4096

	case "$idle_seconds" in *[!0-9]*|'') idle_seconds=300;; esac
	case "$poll_seconds" in *[!0-9]*|'') poll_seconds=5;; esac
	case "$traffic_threshold_bytes" in *[!0-9]*|'') traffic_threshold_bytes=4096;; esac
	[ "$poll_seconds" -gt 0 ] || poll_seconds=5
}

traffic_bytes() {
	awk 'NR > 2 {
		gsub(":", "", $1)
		if ($1 != "lo")
			total += $2 + $10
	} END { printf "%.0f\n", total }' /proc/net/dev
}

enter_suspend() {
	reason="${1:-manual}"
	load_settings
	[ "$enabled" -eq 1 ] || return 0

	grep -qw mem /sys/power/state || {
		logger -t mt76x8-powersave "suspend-to-RAM is unavailable"
		return 1
	}

	mkdir "$LOCK_DIR" 2>/dev/null || return 0
	trap 'rmdir "$LOCK_DIR"' EXIT INT TERM

	logger -t mt76x8-powersave "entering suspend-to-RAM ($reason)"
	sync
	if ! echo mem > /sys/power/state; then
		logger -t mt76x8-powersave "suspend-to-RAM failed"
		return 1
	fi
	logger -t mt76x8-powersave "resumed from suspend-to-RAM"
}

monitor_traffic() {
	load_settings
	[ "$enabled" -eq 1 ] || exit 0
	[ "$idle_seconds" -gt 0 ] || exit 0

	last_bytes="$(traffic_bytes)"
	idle=0

	while sleep "$poll_seconds"; do
		current_bytes="$(traffic_bytes)"
		active="$(awk -v current="$current_bytes" -v last="$last_bytes" \
			-v threshold="$traffic_threshold_bytes" \
			'BEGIN { delta = current - last; print (delta < 0 || delta > threshold) ? 1 : 0 }')"
		last_bytes="$current_bytes"

		if [ "$active" -eq 1 ]; then
			idle=0
		else
			idle=$((idle + poll_seconds))
		fi

		if [ "$idle" -ge "$idle_seconds" ]; then
			enter_suspend "${idle_seconds}s traffic idle"
			last_bytes="$(traffic_bytes)"
			idle=0
		fi
	done
}

case "${1:-}" in
	suspend)
		enter_suspend "${2:-manual}"
		;;
	monitor)
		monitor_traffic
		;;
	*)
		echo "Usage: $0 {suspend [reason]|monitor}" >&2
		exit 1
		;;
esac
