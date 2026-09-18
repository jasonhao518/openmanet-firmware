# EdgeZ subnet routes

This package is selected by boards/common/openmanet_diffconfig, including the
Raspberry Pi builds that include that common configuration. It adds a standard
netifd shell protocol (`edgez_routes`) to consume EdgeZ Alfred announcements.
netifd owns route installation, replacement, and removal; the adapter does not
execute route mutations or repeatedly commit UCI. It publishes local prefixes,
learns remote prefixes, and can own the dynamic mesh default route. First-boot
policy keeps NAT on WAN and creates symmetric Wi-Fi/HaLow forwarding.

On first boot, a UCI defaults script registers network.edgez_routes on
br-ahwlan. It also enables the otherwise-disabled upstream Alfred configuration,
moves it from `br-lan` to `br-ahwlan`, selects `bat0`, and runs every mesh
router as a master for a redundant directory plane. Change the route protocol's
`device` option if the HaLow bridge has another name.
Package release 4 also repairs a preserved older section when its device option
is missing. The protocol itself defaults to br-ahwlan, so route startup does not
depend on a UCI-defaults migration having run. Existing non-empty administrator
settings are not replaced; use `mesh_device` to override the protocol default.
The route process waits for the mesh bridge during boot, so an early netifd
start no longer leaves the protocol permanently down with `NO_DEVICE`.
Options in that interface section:

```
config interface 'edgez_routes'
    option proto 'edgez_routes'
    option device 'br-ahwlan'
    option mesh_device 'br-ahwlan'
    option require_lease '0'
    option leasefile '/tmp/dhcp.leases'
    option socket '/var/run/alfred.sock'
    option local_network 'wifi'
    option gateway_mode '0'
    option manage_default '1'
    option wan_network 'wan'
    option gateway_down_kbps '100000'
    option gateway_up_kbps '100000'
    option status_file '/tmp/edgez-routes-status.json'
```

Alfred runs in primary/master mode on the HaLow bridge. ESP32 nodes send their
records in response to its primary announcements. The bridge must have an IPv4
address; the advertised next hop must be a usable address on that bridge's
subnet. By default the
next-hop address and record MAC can optionally be required to match a live
dnsmasq DHCP lease. Distributed Linux publishers are not clients of one
gateway's DHCP server, so the multi-gateway default disables this legacy check.
Use this mode only on an admitted/trusted mesh until authenticated ownership
records are implemented.

After installing this package into an existing image, register the protocol
by restarting network during a maintenance window. On firmware boot netifd
loads it automatically. Use `ifup edgez_routes`, `ifdown edgez_routes`,
`ubus call network.interface.edgez_routes status`, `ip -4 route`, and
`logread | grep edgez-routes` to inspect it. No separate procd service is needed.

Example learned route: `10.87.212.128/27 via 10.42.0.23 dev br-ahwlan`.
The ESP32 mesh SoftAP must use routed forwarding and accept packets for its
downstream /27. On first install or image boot, this package adds the standard
UCI `ahwlan` to `wan` forwarding, enables IPv4 masquerading on the existing WAN
zone, and enables its MTU fix. A live package upgrade reloads firewall4 after
committing a change. Existing option values are preserved on upgrade, so an
administrator can subsequently override or disable this policy.

Linux nodes also publish the `/27` on `local_network`. Gateways publish Alfred
type 105 while their configured WAN interface is up with a default route. Mesh
points rank the best three records using weighted rendezvous selection and let
netifd install the selected default. Different mesh points therefore distribute
across multiple gateways without a central scheduler. Prefix routes do not
depend on gateway availability. A gateway uses its direct WAN while healthy;
if that WAN fails, it also selects a peer's advertised mesh default so its
local Wi-Fi clients retain Internet access.

The daemon atomically writes its validated, freshness-checked view to
`/tmp/edgez-routes-status.json`. The OpenMANET mesh-topology RPC includes
snapshots no older than 20 seconds. LuCI shows an available remote WiFi subnet
inside the node card, gives a live Internet gateway a green star and border,
and marks the local gateway as WAN-offline when its configured gateway role is
not currently being advertised.

The package also defaults `bat0`, `br-ahwlan`, and the `ahwlan` Layer-3
interface to MTU 1400. This keeps normal IP packets below BATMAN's link-layer
fragmentation threshold because the lightweight ESP32 peer does not consume
Linux `BATADV_UNICAST_FRAG` frames.

## Wire format and freshness

Alfred data type 104, data version 2, ASCII payload (no trailing newline/NUL):

`EZ4R1 <session-id:8hex> <sequence:8hex> <10.x.x.x/27> <DHCP-next-hop> <45-or-0>`

The Alfred record owner is the node's HaLow MAC. Lifetime zero withdraws the
route. This version intentionally rejects the older EZ6D IPv6 directory format.
Sequence advances every polling cycle. The consumer polls every
5 seconds. It requires an advancing sequence after startup/session change and
expires a record after 45 seconds without advancement. Repeated reads of a
cached Alfred value do not extend its lifetime. Route setup can therefore take
two primary-announcement cycles. The session ID changes whenever the publisher
process starts, so a supervised restart cannot be mistaken for a replay after
its sequence counter returns to zero. Planned withdrawal and unexpected power
loss are both handled. DHCP lease changes replace the next hop after validation.

Gateway record, Alfred type 105:

`EZGW1 <session-id:8hex> <sequence:8hex> <transit-IP> <down-kbps> <up-kbps> <load-0..100> <45-or-0>`

Gateway and prefix publishers use the same freshness and withdrawal rules.

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
