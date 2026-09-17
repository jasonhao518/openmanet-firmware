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
	proto_config_add_string local_network
	proto_config_add_boolean gateway_mode
	proto_config_add_boolean manage_default
	proto_config_add_string wan_network
	proto_config_add_int gateway_down_kbps
	proto_config_add_int gateway_up_kbps
	proto_config_add_string node_id
	proto_config_add_string status_file
}

proto_edgez_routes_setup() {
	local config="$1" iface="$2" mesh_device socket leasefile require_lease
	local local_network gateway_mode manage_default wan_network gateway_down_kbps gateway_up_kbps node_id status_file
	json_get_vars mesh_device socket leasefile require_lease local_network gateway_mode manage_default
	json_get_vars wan_network gateway_down_kbps gateway_up_kbps node_id status_file
	# netifd normally supplies the resolved L3 device as $2. Preserve support
	# for profiles created by the first package revision, which could retain an
	# edgez_routes section without its device option across a sysupgrade.
	[ -n "$iface" ] || iface="$mesh_device"
	[ -n "$iface" ] || iface="$(uci -q get network."$config".device)"
	[ -n "$iface" ] || iface=br-ahwlan
	[ -n "$socket" ] || socket=/var/run/alfred.sock
	[ -n "$leasefile" ] || leasefile=/tmp/dhcp.leases
	[ -n "$wan_network" ] || wan_network=wan
	[ -n "$gateway_down_kbps" ] || gateway_down_kbps=100000
	[ -n "$gateway_up_kbps" ] || gateway_up_kbps=100000
	[ -n "$status_file" ] || status_file=/tmp/edgez-routes-status.json
	local lease_arg="" local_arg="" gateway_arg="" default_arg="" node_arg=""
	[ "$require_lease" = 0 ] && lease_arg=--no-lease-check
	[ -n "$local_network" ] && local_arg="--local-network $local_network"
	[ "$gateway_mode" = 1 ] && gateway_arg=--gateway-mode
	[ "$manage_default" = 1 ] && default_arg=--manage-default
	[ -n "$node_id" ] && node_arg="--node-id $node_id"
	proto_run_command "$config" /usr/sbin/edgez-subnet-routes \
		--network "$config" --interface "$iface" --socket "$socket" --leasefile "$leasefile" \
		--wan-network "$wan_network" --gateway-down-kbps "$gateway_down_kbps" \
		--gateway-up-kbps "$gateway_up_kbps" --status-file "$status_file" \
		$lease_arg $local_arg $gateway_arg $default_arg $node_arg
}

proto_edgez_routes_teardown() {
	proto_kill_command "$1"
}

add_protocol edgez_routes
