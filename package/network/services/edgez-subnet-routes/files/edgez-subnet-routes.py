#!/usr/bin/python3
"""Publish/reconcile EdgeZ prefixes and select distributed Internet gateways."""
import argparse
import hashlib
import ipaddress
import json
import logging
import math
import re
import signal
import subprocess
import time
import uuid
from pathlib import Path

ROW = re.compile(r'\{\s*"([0-9a-fA-F:]{17})"\s*,\s*"([^"\r\n]*)"\s*\}')
WIRE = re.compile(r'EZ4R1 ([0-9a-f]{8}) ([0-9a-f]{8}) (10\.[0-9.]+/27) ([0-9.]+) (0|45)')
GATEWAY_WIRE = re.compile(
    r'EZGW1 ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9.]+) '
    r'([1-9][0-9]{0,8}) ([1-9][0-9]{0,8}) ([0-9]{1,3}) (0|45)')


def records(text):
    result = {}
    if len(text) > 262144:
        raise ValueError('Alfred response too large')
    for owner, escaped in ROW.findall(text):
        owner = owner.lower()
        if int(owner[:2], 16) & 1 or owner == '00:00:00:00:00:00':
            continue
        value = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), escaped)
        match = WIRE.fullmatch(value)
        if not match:
            continue
        boot, sequence, subnet, hop, ttl = match.groups()
        try:
            net = ipaddress.IPv4Network(subnet, strict=True)
            gateway = ipaddress.IPv4Address(hop)
        except ValueError:
            continue
        if net.prefixlen != 27 or not net.subnet_of(ipaddress.IPv4Network('10.80.0.0/12')):
            continue
        if net.overlaps(ipaddress.IPv4Network('10.42.0.0/24')) or net.overlaps(ipaddress.IPv4Network('10.43.0.0/24')):
            continue
        if gateway.is_multicast or gateway.is_unspecified or gateway.is_loopback or gateway.is_link_local:
            continue
        result[owner] = (boot, int(sequence, 16), net, gateway, int(ttl))
    return result


def gateway_records(text):
    result = {}
    if len(text) > 262144:
        raise ValueError('Alfred response too large')
    for owner, escaped in ROW.findall(text):
        owner = owner.lower()
        if int(owner[:2], 16) & 1 or owner == '00:00:00:00:00:00':
            continue
        value = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), escaped)
        match = GATEWAY_WIRE.fullmatch(value)
        if not match:
            continue
        boot, sequence, hop, down, up, load, ttl = match.groups()
        try:
            gateway = ipaddress.IPv4Address(hop)
            down, up, load, ttl = int(down), int(up), int(load), int(ttl)
        except ValueError:
            continue
        if gateway.is_multicast or gateway.is_unspecified or gateway.is_loopback or gateway.is_link_local:
            continue
        if load > 100:
            continue
        result[owner] = (boot, int(sequence, 16), gateway, down, up, load, ttl)
    return result


class Freshness:
    """A cached first sample is insufficient; observe an advancing sequence."""
    def __init__(self):
        self.nodes = {}

    def update(self, incoming, now):
        for owner, record in incoming.items():
            boot, seq, ttl = record[0], record[1], record[-1]
            previous = self.nodes.get(owner)
            if previous is None or previous[0][0] != boot:
                if previous is None and len(self.nodes) >= 512:
                    continue
                self.nodes[owner] = (record, now, False)
                continue
            old, seen, confirmed = previous
            delta = (seq - old[1]) & 0xffffffff
            if 0 < delta < 0x80000000:
                self.nodes[owner] = (record, now, ttl != 0)
        return {owner: r for owner, (r, seen, confirmed) in self.nodes.items()
                if confirmed and r[-1] and now - seen < r[-1]}

    def recent(self, now, maximum_age=45):
        """Return advancing records even when they intentionally withdraw service."""
        return {owner: record for owner, (record, seen, _) in self.nodes.items()
                if now - seen < maximum_age}


def leases(path, now):
    result = set()
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            expires = int(fields[0])
            ip = ipaddress.IPv4Address(fields[2])
        except ValueError:
            continue
        if expires == 0 or expires > now:
            result.add((fields[1].lower(), ip))
    return result


def desired_routes(active, addresses, existing, lease_set, owned=None):
    desired = {}
    owned = owned or {}
    networks = []
    local = set()
    for item in addresses:
        for addr in item.get('addr_info', []):
            if addr.get('family') == 'inet':
                interface = ipaddress.IPv4Interface(f"{addr['local']}/{addr['prefixlen']}")
                networks.append(interface.network)
                local.add(interface.ip)
    for owner, (_, _, net, hop, _) in active.items():
        if hop in local or not any(hop in transit and hop not in (transit.network_address, transit.broadcast_address) for transit in networks):
            continue
        if lease_set is not None and (owner, hop) not in lease_set:
            continue
        if any(other_owner != owner and net.overlaps(other[2]) for other_owner, other in active.items()):
            continue
        if any(net.overlaps(transit) for transit in networks):
            continue
        conflict = False
        for route in existing:
            if (owned.get(route.get('dst')) == route.get('gateway') and route.get('dst') in owned) or route.get('dst', 'default') == 'default':
                continue
            try:
                if net.overlaps(ipaddress.IPv4Network(route['dst'])):
                    conflict = True
            except ValueError:
                pass
        if not conflict:
            desired[str(net)] = str(hop)
    return desired


def on_link_hops(active, addresses):
    networks = []
    local = set()
    for item in addresses:
        for addr in item.get('addr_info', []):
            if addr.get('family') == 'inet':
                interface = ipaddress.IPv4Interface(f"{addr['local']}/{addr['prefixlen']}")
                networks.append(interface.network)
                local.add(interface.ip)
    return {
        owner: record for owner, record in active.items()
        if record[2] not in local and any(
            record[2] in transit and record[2] not in (transit.network_address, transit.broadcast_address)
            for transit in networks)
    }


def rank_gateways(active, addresses, node_id, path_quality=None):
    """Weighted rendezvous order: stable distribution without a central scheduler."""
    ranked = []
    for owner, record in on_link_hops(active, addresses).items():
        _, _, hop, down, up, load, _ = record
        if path_quality is not None and owner not in path_quality:
            continue
        tq = 255 if path_quality is None else path_quality[owner]
        capacity = max(1, min(down, up)) * max(1, 100 - load) * max(1, tq * tq)
        digest = hashlib.sha256(f'{node_id}|{owner}'.encode()).digest()
        uniform = (int.from_bytes(digest[:8], 'big') + 1) / ((1 << 64) + 1)
        score = capacity / -math.log(uniform)
        ranked.append((score, owner, str(hop)))
    ranked.sort(reverse=True)
    return ranked


def use_mesh_default(manage_default, gateway_mode, local_wan_ready):
    """Clients always select a gateway; servers do so only as WAN fallback."""
    return manage_default or (gateway_mode and not local_wan_ready)


def status_snapshot(active, active_gateways, gateway_roles=None, mesh_macs=None,
                    local_prefix=None, gateway_mode=False, local_wan_ready=False,
                    now=None):
    """Build the small, validated directory consumed by the LuCI topology."""
    nodes = {}
    for owner, (_, _, subnet, hop, _) in active.items():
        router = ipaddress.IPv4Interface(
            f'{subnet.network_address + 1}/{subnet.prefixlen}')
        nodes[owner] = {'wifi_subnet': str(subnet),
                        'wifi_router': str(router),
                        'transit_ip': str(hop)}
    for owner, (_, _, hop, _, _, _, _) in (gateway_roles or {}).items():
        node = nodes.setdefault(owner, {'transit_ip': str(hop)})
        node['gateway_role'] = True
    for owner, (_, _, hop, _, _, _, _) in active_gateways.items():
        node = nodes.setdefault(owner, {'transit_ip': str(hop)})
        node['gateway_role'] = True
        node['internet_gateway'] = True
    for owner, mesh_mac in (mesh_macs or {}).items():
        if owner in nodes:
            nodes[owner]['mesh_mac'] = mesh_mac
    local = {'gateway_role': gateway_mode,
             'internet_gateway': gateway_mode and local_wan_ready}
    if local_prefix:
        if isinstance(local_prefix, ipaddress.IPv4Interface):
            local_interface = local_prefix
        else:
            network = ipaddress.IPv4Network(local_prefix)
            local_interface = ipaddress.IPv4Interface(
                f'{network.network_address + 1}/{network.prefixlen}')
        local['wifi_subnet'] = str(local_interface.network)
        local['wifi_router'] = str(local_interface)
    return {'version': 1, 'updated_at': time.time() if now is None else now,
            'local': local, 'nodes': nodes}


def write_status(path, snapshot):
    target = Path(path)
    temporary = Path(f'{path}.tmp')
    temporary.write_text(json.dumps(snapshot, separators=(',', ':')))
    temporary.replace(target)


class GatewaySelector:
    def __init__(self, improvement=1.20, hold_seconds=10):
        self.current = None
        self.last_switch = float('-inf')
        self.improvement = improvement
        self.hold_seconds = hold_seconds

    def update(self, ranked, now):
        available = {owner: (score, hop) for score, owner, hop in ranked}
        if self.current not in available:
            self.current = ranked[0][1] if ranked else None
            self.last_switch = now
        elif ranked and ranked[0][1] != self.current and now - self.last_switch >= self.hold_seconds:
            current_score = available[self.current][0]
            if ranked[0][0] > current_score * self.improvement:
                self.current = ranked[0][1]
                self.last_switch = now
        return available[self.current][1] if self.current in available else None


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=5).stdout


def notify(network, interface, desired, default_gateway=None, up=True):
    # Same schema as netifd-proto.sh proto_init_update/proto_add_ipv4_route.
    # netifd replaces only this protocol interface's route set.
    payload = {'action': 0, 'interface': network, 'ifname': interface,
               'link-up': up, 'address-external': True, 'keep': False,
               'routes': [{'target': str(ipaddress.IPv4Network(net).network_address),
                           'netmask': '27', 'gateway': hop}
                          for net, hop in sorted(desired.items())]}
    if default_gateway:
        payload['routes'].append({'target': '0.0.0.0', 'netmask': '0',
                                  'gateway': default_gateway})
    run('ubus', 'call', 'network.interface', 'notify_proto', json.dumps(payload))


def interface_addresses(interface):
    return json.loads(run('ip', '-j', '-4', 'address', 'show', 'dev', interface))


def batman_gateway_quality(mesh='bat0'):
    result = {}
    for row in json.loads(run('batctl', 'meshif', mesh, 'gateways_json')):
        owner = str(row.get('orig_address', '')).lower()
        try:
            tq = int(row['tq'])
        except (KeyError, TypeError, ValueError):
            continue
        if re.fullmatch(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}', owner) and 0 < tq <= 255:
            result[owner] = tq
    return result


def batman_client_origins(mesh='bat0'):
    """Map BATMAN translation-table clients (bridge MACs) to originators."""
    result = {}
    for row in json.loads(run('batctl', 'meshif', mesh, 'transtable_global_json')):
        owner = str(row.get('tt_address', '')).lower()
        origin = str(row.get('orig_address', '')).lower()
        if not row.get('best', True):
            continue
        if (re.fullmatch(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}', owner) and
                re.fullmatch(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}', origin)):
            result[owner] = origin
    return result


def correlate_gateway_quality(active_gateways, path_quality, client_origins):
    """Key originator TQ values by the Alfred record owner used for ranking."""
    return {
        owner: path_quality[client_origins.get(owner, owner)]
        for owner in active_gateways
        if client_origins.get(owner, owner) in path_quality
    }


def interface_network(network):
    status = json.loads(run('ubus', 'call', f'network.interface.{network}', 'status'))
    for address in status.get('ipv4-address', []):
        try:
            interface = ipaddress.IPv4Interface(f"{address['address']}/{address['mask']}")
        except (KeyError, ValueError):
            continue
        if interface.network.prefixlen == 27 and interface.network.subnet_of(
                ipaddress.IPv4Network('10.80.0.0/12')):
            return interface
    return None


def first_address(addresses):
    for item in addresses:
        for addr in item.get('addr_info', []):
            if addr.get('family') == 'inet':
                return ipaddress.IPv4Address(addr['local'])
    return None


def wan_ready(network):
    status = json.loads(run('ubus', 'call', f'network.interface.{network}', 'status'))
    if not status.get('up'):
        return False
    return any(route.get('target') == '0.0.0.0' and int(route.get('mask', -1)) == 0
               for route in status.get('route', []))


def publish(socket, data_type, payload):
    subprocess.run(('alfred', '-u', socket, '-s', str(data_type)), input=payload,
                   check=True, capture_output=True, text=True, timeout=5)


def session_id():
    # This is a publisher-session ID, not merely a kernel boot ID.  A supervised
    # route process can restart while the router remains up, resetting sequence
    # to zero.  Reusing the kernel boot ID would make peers reject every new
    # record as a replay until their own daemon restarted.
    return uuid.uuid4().hex[:8]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--network', required=True)
    parser.add_argument('--interface', default='br-ahwlan')
    parser.add_argument('--leasefile', default='/tmp/dhcp.leases')
    parser.add_argument('--socket', default='/var/run/alfred.sock')
    parser.add_argument('--no-lease-check', action='store_true')
    parser.add_argument('--local-network')
    parser.add_argument('--gateway-mode', action='store_true')
    parser.add_argument('--manage-default', action='store_true')
    parser.add_argument('--wan-network', default='wan')
    parser.add_argument('--gateway-down-kbps', type=int, default=100000)
    parser.add_argument('--gateway-up-kbps', type=int, default=100000)
    parser.add_argument('--node-id')
    parser.add_argument('--status-file', default='/tmp/edgez-routes-status.json')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='edgez-routes: %(message)s')
    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    freshness = Freshness()
    gateway_freshness = Freshness()
    published = {}
    selected_gateway = None
    last_candidates = []
    selector = GatewaySelector()
    registered = False
    session = session_id()
    sequence = 0
    last_local_hop = None
    node_id = args.node_id
    try:
        # This protocol is started with the rest of netifd, often just before
        # the BATMAN bridge is created. Keep the supervised process alive and
        # wait for the configured device instead of turning that normal boot
        # ordering into a permanent protocol failure.
        waiting_logged = False
        while running:
            try:
                addresses = interface_addresses(args.interface)
                break
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                if not waiting_logged:
                    logging.warning('waiting for interface %s: %s', args.interface, error)
                    waiting_logged = True
                time.sleep(1)
        if not running:
            return
        # Relearn after a daemon restart; disk/cache age is not publication age.
        notify(args.network, args.interface, {})
        registered = True
        while running:
            sequence = (sequence + 1) & 0xffffffff
            try:
                incoming = records(run('alfred', '-u', args.socket, '-r', '104'))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                logging.warning('Alfred unavailable: %s', error)
                incoming = {}
            active = freshness.update(incoming, time.monotonic())
            try:
                gateway_incoming = gateway_records(run('alfred', '-u', args.socket, '-r', '105'))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                logging.warning('gateway directory unavailable: %s', error)
                gateway_incoming = {}
            directory_now = time.monotonic()
            active_gateways = gateway_freshness.update(gateway_incoming, directory_now)
            gateway_roles = gateway_freshness.recent(directory_now)
            try:
                addresses = interface_addresses(args.interface)
                local_prefix = None
                local_wan_ready = False
                local_hop = first_address(addresses)
                if local_hop:
                    last_local_hop = local_hop
                if node_id is None:
                    try:
                        node_id = Path(f'/sys/class/net/{args.interface}/address').read_text().strip()
                    except OSError:
                        node_id = str(last_local_hop or args.interface)

                if args.local_network and last_local_hop:
                    try:
                        local_prefix = interface_network(args.local_network)
                        if local_prefix:
                            publish(args.socket, 104,
                                    f'EZ4R1 {session} {sequence:08x} {local_prefix.network} '
                                    f'{last_local_hop} 45')
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        logging.warning('local prefix publication failed: %s', error)

                if args.gateway_mode and last_local_hop:
                    try:
                        local_wan_ready = wan_ready(args.wan_network)
                        publish(args.socket, 105,
                                f'EZGW1 {session} {sequence:08x} {last_local_hop} '
                                f'{args.gateway_down_kbps} {args.gateway_up_kbps} 0 '
                                f'{45 if local_wan_ready else 0}')
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        logging.warning('gateway publication failed: %s', error)
                existing = json.loads(run('ip', '-j', '-4', 'route', 'show', 'table', 'main'))
                lease_set = None if args.no_lease_check else leases(args.leasefile, time.time())
                desired = desired_routes(active, addresses, existing, lease_set, published)
                try:
                    origin_quality = batman_gateway_quality()
                    client_origins = batman_client_origins()
                    path_quality = correlate_gateway_quality(
                        active_gateways, origin_quality, client_origins)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    logging.warning('BATMAN gateway quality unavailable: %s', error)
                    path_quality = None
                    client_origins = {}
                ranked = rank_gateways(active_gateways, addresses, node_id, path_quality)
                if not ranked and active_gateways and path_quality:
                    # Some Alfred builds identify a record by the bridge MAC
                    # rather than BATMAN's originator MAC. Preserve routing and
                    # log the missing correlation instead of black-holing WAN.
                    logging.warning('gateway records did not match BATMAN originators; using directory metrics')
                    ranked = rank_gateways(active_gateways, addresses, node_id)
                candidates = [(owner, hop, round(score)) for score, owner, hop in ranked[:3]]
                default_gateway = (selector.update(ranked, time.monotonic())
                                   if use_mesh_default(args.manage_default,
                                                       args.gateway_mode,
                                                       local_wan_ready)
                                   else None)
                if candidates != last_candidates:
                    logging.info('gateway candidates: %s', candidates)
                    last_candidates = candidates
                try:
                    write_status(args.status_file,
                                 status_snapshot(active, active_gateways, gateway_roles,
                                                 client_origins, local_prefix,
                                                 args.gateway_mode, local_wan_ready))
                except OSError as error:
                    logging.warning('topology status update failed: %s', error)
                if desired != published or default_gateway != selected_gateway:
                    notify(args.network, args.interface, desired, default_gateway)
                    logging.info('netifd routes: prefixes=%s default=%s', desired, default_gateway)
                    published = desired
                    selected_gateway = default_gateway
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                logging.warning('route validation failed: %s', error)
                # Never retain routes after their interface/lease validation fails.
                try:
                    notify(args.network, args.interface, {})
                except (OSError, subprocess.SubprocessError) as notify_error:
                    logging.warning('route withdrawal failed: %s', notify_error)
                published = {}
                selected_gateway = None
            for _ in range(5):
                if not running:
                    break
                time.sleep(1)
    finally:
        if registered:
            try:
                if args.local_network and last_local_hop:
                    local_prefix = interface_network(args.local_network)
                    if local_prefix:
                        publish(args.socket, 104,
                                f'EZ4R1 {session} {(sequence + 1) & 0xffffffff:08x} '
                                f'{local_prefix} {last_local_hop} 0')
                if args.gateway_mode and last_local_hop:
                    publish(args.socket, 105,
                            f'EZGW1 {session} {(sequence + 1) & 0xffffffff:08x} '
                            f'{last_local_hop} {args.gateway_down_kbps} '
                            f'{args.gateway_up_kbps} 0 0')
                notify(args.network, args.interface, {}, up=False)
            except (OSError, subprocess.SubprocessError):
                pass
        try:
            Path(args.status_file).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


if __name__ == '__main__':
    main()
