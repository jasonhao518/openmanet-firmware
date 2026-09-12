# EdgeZ subnet routes

This package is selected by boards/common/openmanet_diffconfig, including the
Raspberry Pi builds that include that common configuration. It adds a standard
netifd shell protocol (`edgez_routes`) to consume EdgeZ Alfred announcements.
netifd owns route installation, replacement, and removal; the adapter does not
execute route mutations or repeatedly commit UCI. It leaves existing interfaces,
addresses, DHCP configuration, default routes, and firewall policies intact.

On first boot, a UCI defaults script registers network.edgez_routes on
br-ahwlan. Change its `device` option if the HaLow bridge has another name.
Package release 2 also repairs a preserved release-1 section when its device
option is missing; existing non-empty administrator settings are not replaced.
Options in that interface section:

```
config interface 'edgez_routes'
    option proto 'edgez_routes'
    option device 'br-ahwlan'
    option require_lease '1'
    option leasefile '/tmp/dhcp.leases'
    option socket '/var/run/alfred.sock'
```

Alfred must run in primary/master mode on the HaLow bridge, as configured by
OpenMANET's Alfred package. ESP32 nodes send their records in response to its
primary announcements. The bridge must have an IPv4 address; the advertised
next hop must be a usable address on that bridge's subnet. By default the
next-hop address and record MAC must match a live dnsmasq DHCP lease. On routers
using another DHCP server, configure a compatible lease file; disable
require_lease only for a trusted mesh where equivalent validation is provided.

After installing this package into an existing image, register the protocol
by restarting network during a maintenance window. On firmware boot netifd
loads it automatically. Use `ifup edgez_routes`, `ifdown edgez_routes`,
`ubus call network.interface.edgez_routes status`, `ip -4 route`, and
`logread | grep edgez-routes` to inspect it. No separate procd service is needed.

Example learned route: `10.87.212.128/27 via 10.42.0.23 dev br-ahwlan`.
The ESP32 mesh SoftAP must use routed forwarding and accept packets for its
downstream /27. WAN masquerading belongs on the OpenWrt Internet gateway.
Existing OpenWrt firewall rules must allow forwarding from the HaLow bridge's
zone to itself and to WAN, and WAN masquerading must include downstream source
subnets. This package does not override administrator firewall policy.

## Wire format and freshness

Alfred data type 104, data version 2, ASCII payload (no trailing newline/NUL):

`EZ4R1 <boot-id:8hex> <sequence:8hex> <10.x.x.x/27> <DHCP-next-hop> <45-or-0>`

The Alfred record owner is the node's HaLow MAC. Lifetime zero withdraws the
route. This version intentionally rejects the older EZ6D IPv6 directory format.
Sequence advances every 10 seconds and on IP changes. The consumer polls every
5 seconds. It requires an advancing sequence after startup/session change and
expires a record after 45 seconds without advancement. Repeated reads of a
cached Alfred value do not extend its lifetime. Route setup can therefore take
two primary-announcement cycles. Planned withdrawal and unexpected power loss
are both handled. DHCP lease changes replace the next hop after validation.

Conflicting owners, malformed records, off-link next hops, overlapping connected
or existing routes, and built-in 10.42.0.0/24 / 10.43.0.0/24 transit ranges are
rejected. Alfred provides discovery within an admitted mesh, not cryptographic
route authentication; only use this on a trusted mesh.

## Validation

Run `python3 package/network/services/edgez-subnet-routes/test_routes.py` on a
host. Build the firmware normally, or use
`make package/network/services/edgez-subnet-routes/compile V=s` in a configured
OpenWrt build environment. Test on two ESP32s and the Pi: bidirectional client
ping/iperf, WAN access, changed DHCP lease, node shutdown, duplicate subnet,
network restart, and stale Alfred cache after restarting the protocol.
