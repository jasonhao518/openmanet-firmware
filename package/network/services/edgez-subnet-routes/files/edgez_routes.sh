#!/bin/sh
. /lib/functions.sh
. ../netifd-proto.sh
init_proto "$@"

proto_edgez_routes_init_config() {
	available=1
	proto_config_add_string socket
	proto_config_add_string leasefile
	proto_config_add_boolean require_lease
}

proto_edgez_routes_setup() {
	local config="$1" iface="$2" socket leasefile require_lease
	json_get_vars socket leasefile require_lease
	[ -n "$socket" ] || socket=/var/run/alfred.sock
	[ -n "$leasefile" ] || leasefile=/tmp/dhcp.leases
	local extra=""
	[ "$require_lease" = 0 ] && extra=--no-lease-check
	proto_run_command "$config" /usr/sbin/edgez-subnet-routes \
		--network "$config" --interface "$iface" --socket "$socket" --leasefile "$leasefile" $extra
}

proto_edgez_routes_teardown() {
	proto_kill_command "$1"
}

add_protocol edgez_routes
