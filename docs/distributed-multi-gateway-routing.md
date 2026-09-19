# Distributed routed mesh and multiple gateways

## Objective

H7608 and Raspberry Pi nodes form one HaLow/BATMAN transit network while each
local Wi-Fi AP owns a distinct routed IPv4 `/27`. Internal traffic goes directly
to the node that owns the destination prefix. Internet traffic uses one of
several independently advertised gateways, so no fixed gateway is required for
mesh connectivity.

The HaLow BATMAN_IV profile uses TTL 8 and hop penalty 30. Each forwarded hop
therefore multiplies TQ by `225/255`; ESP32 route selection uses a 20-point TQ
hysteresis before switching next hops. Upgraded ESP32 relays clamp legacy
TTL-50 traffic to the new limit, allowing a bounded rolling deployment.

This is split into two routing decisions:

1. A specific `10.80.0.0/12` `/27` always routes to its owning mesh node.
2. Only the default route selects an Internet gateway.

Mesh points selectively masquerade only public destinations when forwarding
from their local Wi-Fi subnet to HaLow. Destinations inside `10.0.0.0/8` are
never masqueraded, so upgraded nodes retain end-to-end addressing and can
route between downstream subnets. The public-only rule also permits migration
through an older gateway that has not learned the new downstream `/27` yet.

## Address plan

| Range | Use |
| --- | --- |
| `10.41.0.0/16` | HaLow/BATMAN transit addresses and gateway DHCP bands |
| `10.41.254.0/24` | Stable Linux mesh-point addresses during migration |
| `10.80.0.0/12` | MAC-derived, persistent downstream Wi-Fi/SoftAP `/27`s |

A gateway uses a stable `10.41.<slot>.1/16` transit address. Its temporary DHCP
allocation band starts at `10.41.<slot>.100`; this prevents two gateways from
allocating from the same pool in the normal case. MAC derivation is an initial
candidate, not a mathematical uniqueness guarantee. A later phase must add
signed ownership records and deterministic collision recovery.

## Control-plane records

Alfred remains the first implementation transport. Records advance every five
seconds and expire after 45 seconds. A cached first observation is not trusted;
the sequence must advance before a record becomes active.

The OpenWrt package defaults are not usable unchanged: Alfred ships disabled
and attached to `br-lan`. The route package enables it on `br-ahwlan`, with
`bat0` as its BATMAN interface. Every H7608 and Raspberry Pi node runs as an
Alfred master. Multiple masters exchange records, so loss of one gateway does
not also remove a central route-directory service.

### Downstream prefix: Alfred type 104

```text
EZ4R1 <boot:8hex> <sequence:8hex> <network/27> <transit-next-hop> <0-or-45>
```

Both ESP32 and Linux nodes publish this record. Every OpenWrt node consumes it
and netifd owns the resulting route set.

### Internet gateway: Alfred type 105

```text
EZGW1 <boot:8hex> <sequence:8hex> <transit-ip> <down-kbps> <up-kbps> <load-percent> <0-or-45>
```

A Linux gateway advertises lifetime 45 only while its WAN interface is up and
contains a default route. A withdrawal uses lifetime zero. Gateway capacity and
load and live BATMAN path quality participate in selection. Active WAN and DNS
probes are planned inputs.

## Gateway selection

Every mesh point keeps the best three valid candidates. Weighted rendezvous
selection uses the stable node identity, gateway identity, advertised capacity
and load, plus squared BATMAN TQ. A 20% improvement threshold and ten-second
hold time prevent ordinary metric noise from causing rapid switching. This
distributes different mesh nodes across gateways without a central scheduler.

The first implementation installs one active default per mesh point. A gateway
keeps its direct WAN default while that WAN is healthy, but installs a selected
mesh default if its own WAN fails. The other two candidates remain warm
control-plane entries. This already makes multiple gateways active across the
deployment and keeps a failed gateway's local Wi-Fi usable through a peer.

Using two gateways concurrently from one node is phase two. It requires:

- one policy-routing table per selected gateway;
- nftables connection marks assigned only on a new flow;
- restoration of packet marks from connection marks;
- stable five-tuple or client hashing, never per-packet balancing;
- removal of failed tables for new flows while surviving conntrack entries age.

NAT state is local to a gateway. Existing Internet connections normally restart
after gateway failure unless a future tunnel anchor or NAT-state replication is
added.

## Firewall policy

| Source | Destination | Forward | NAT |
| --- | --- | --- | --- |
| `wifi` | `ahwlan` on a mesh point | yes | public destinations only; never `10.0.0.0/8` |
| `ahwlan` | `wifi` | yes | no |
| `ahwlan` | `wan` on a gateway | yes | WAN only |
| `wifi` | `wan` on the same gateway | yes | WAN only |

Wi-Fi clients use their local router as DHCP router and DNS server. dnsmasq
forwards external lookups through the currently selected default route.

## Rollout

1. Deploy consumers and publishers while inspecting learned records and routes.
2. Confirm unique transit IPs, gateway DHCP bands and downstream `/27`s.
3. Confirm every gateway and mesh point learns every remote `/27`.
4. Confirm gateways use `ahwlan.masq=0` and `wan.masq=1`. Mesh points use
   `ahwlan.masq=1` with `masq_dest='!10.0.0.0/8'`.
5. Test bidirectional traffic between two downstream Wi-Fi networks.
6. Connect two gateways to the same WAN and verify different mesh nodes select
   different defaults.
7. Disconnect one gateway WAN and verify its record withdraws and affected
   nodes select another gateway; internal routes must remain unchanged.
8. Add per-flow active-active policy routing only after the single-default
   behavior is stable under repeated failure testing.
9. Replace trusted Alfred admission with authenticated records, and later move
   distribution into a replicated BATMAN TVLV if required.

## Device verification

```sh
uci show network.edgez_routes
uci show alfred.alfred
ip -4 address show dev br-ahwlan
ip -4 route show table main
alfred -r 104
alfred -r 105
logread | grep edgez-routes
uci show firewall | grep -E 'wifi|ahwlan|wan|masq'
batctl meshif bat0 gateways
```

Expected results are remote `/27` routes through `br-ahwlan`, one dynamic
default on a mesh point, and source preservation for every private mesh route.
A high-metric route through legacy `10.41.0.1` is retained on H7608 mesh points
during migration; a type-105 learned default has the better metric and wins.
A gateway has no dynamic mesh default while its own WAN is healthy, but gains
one after that WAN fails.
`alfred.alfred` must be enabled, use `br-ahwlan`, use `bat0`, and run in master
mode.

The LuCI mesh topology reads the daemon's validated runtime snapshot. When an
Alfred owner MAC matches the mesh node MAC, its card shows the advertised WiFi
`/27`. Active Internet gateways have a green star and border. The local node
also shows an amber `Gateway (WAN offline)` marker when it has gateway role but
its WAN readiness check is failing. The UI ignores snapshots older than 20
seconds rather than displaying stale route or gateway data.

## Current boundaries

- Alfred records are trusted-mesh discovery, not cryptographic authorization.
- MAC-derived address candidates can collide and need operational conflict
  reporting before large deployments.
- Gateway readiness currently checks WAN interface/default-route state; active
  Internet and DNS probes are not yet part of the score.
- This release distributes nodes between gateways. Per-flow active-active use
  of two gateways from one node is the next implementation phase.
