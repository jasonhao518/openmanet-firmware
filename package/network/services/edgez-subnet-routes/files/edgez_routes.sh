#!/bin/sh
. /lib/functions.sh
. ../netifd-proto.sh
init_proto "$@"

proto_edgez_routes_init_config() {
	available=1
	proto_config_add_string mesh_device
	proto_config_add_string socket
	proto_config_add_string leasefile
	proto_config_add_boolean require_lease
}

proto_edgez_routes_setup() {
	local config="$1" iface="$2" mesh_device socket leasefile require_lease
	json_get_vars mesh_device socket leasefile require_lease
	# netifd normally supplies the resolved L3 device as $2. Preserve support
	# for profiles created by the first package revision, which could retain an
	# edgez_routes section without its device option across a sysupgrade.
	[ -n "$iface" ] || iface="$mesh_device"
	[ -n "$iface" ] || iface="$(uci -q get network."$config".device)"
	[ -n "$iface" ] || iface=br-ahwlan
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
