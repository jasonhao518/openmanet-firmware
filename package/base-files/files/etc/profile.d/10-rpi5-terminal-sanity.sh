#!/bin/sh

# Repair terminal line discipline for interactive Raspberry Pi 5 logins.
# This covers both the HDMI tty and an SSH PTY without affecting scripts or
# other OpenMANET targets.

[ -t 0 ] || return 0
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = 'raspberrypi,5-model-b' ] || return 0
command -v stty >/dev/null 2>&1 || return 0

# Canonical input makes the kernel deliver a complete line after Enter. It
# also restores local echo and normal CR/LF, interrupt, erase and kill keys.
stty sane 2>/dev/null
stty icanon echo echoe echok icrnl onlcr ixon \
	erase '^?' intr '^C' kill '^U' eof '^D' 2>/dev/null

# A previous application can leave bracketed-paste mode enabled in the client
# terminal. Disable it so pasted commands reach BusyBox ash as plain text.
printf '\033[?2004l'
