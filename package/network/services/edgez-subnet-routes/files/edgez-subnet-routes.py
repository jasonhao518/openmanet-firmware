#!/usr/bin/python3
"""Reconcile leased EdgeZ /27 routes from Alfred type 104, wire version EZ4R1."""
import argparse
import ipaddress
import json
import logging
import re
import signal
import subprocess
import time
from pathlib import Path

ROW = re.compile(r'\{\s*"([0-9a-fA-F:]{17})"\s*,\s*"([^"\r\n]*)"\s*\}')
WIRE = re.compile(r'EZ4R1 ([0-9a-f]{8}) ([0-9a-f]{8}) (10\.[0-9.]+/27) ([0-9.]+) (0|45)')


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
        if net.prefixlen != 27 or not net.subnet_of(ipaddress.IPv4Network('10.0.0.0/8')):
            continue
        if net.overlaps(ipaddress.IPv4Network('10.42.0.0/24')) or net.overlaps(ipaddress.IPv4Network('10.43.0.0/24')):
            continue
        if gateway.is_multicast or gateway.is_unspecified or gateway.is_loopback or gateway.is_link_local:
            continue
        result[owner] = (boot, int(sequence, 16), net, gateway, int(ttl))
    return result


class Freshness:
    """A cached first sample is insufficient; observe an advancing sequence."""
    def __init__(self):
        self.nodes = {}

    def update(self, incoming, now):
        for owner, record in incoming.items():
            boot, seq, net, hop, ttl = record
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
                if confirmed and r[4] and now - seen < r[4]}


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


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=5).stdout


def notify(network, interface, desired, up=True):
    # Same schema as netifd-proto.sh proto_init_update/proto_add_ipv4_route.
    # netifd replaces only this protocol interface's route set.
    payload = {'action': 0, 'interface': network, 'ifname': interface,
               'link-up': up, 'address-external': True, 'keep': False,
               'routes': [{'target': str(ipaddress.IPv4Network(net).network_address),
                           'netmask': '27', 'gateway': hop}
                          for net, hop in sorted(desired.items())]}
    run('ubus', 'call', 'network.interface', 'notify_proto', json.dumps(payload))


def interface_addresses(interface):
    return json.loads(run('ip', '-j', '-4', 'address', 'show', 'dev', interface))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--network', required=True)
    parser.add_argument('--interface', default='br-ahwlan')
    parser.add_argument('--leasefile', default='/tmp/dhcp.leases')
    parser.add_argument('--socket', default='/var/run/alfred.sock')
    parser.add_argument('--no-lease-check', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='edgez-routes: %(message)s')
    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    freshness = Freshness()
    published = {}
    registered = False
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
            try:
                incoming = records(run('alfred', '-u', args.socket, '-r', '104'))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                logging.warning('Alfred unavailable: %s', error)
                incoming = {}
            active = freshness.update(incoming, time.monotonic())
            try:
                addresses = interface_addresses(args.interface)
                existing = json.loads(run('ip', '-j', '-4', 'route', 'show', 'table', 'main'))
                lease_set = None if args.no_lease_check else leases(args.leasefile, time.time())
                desired = desired_routes(active, addresses, existing, lease_set, published)
                if desired != published:
                    notify(args.network, args.interface, desired)
                    logging.info('netifd routes: %s', desired)
                    published = desired
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                logging.warning('route validation failed: %s', error)
                # Never retain routes after their interface/lease validation fails.
                notify(args.network, args.interface, {})
                published = {}
            for _ in range(5):
                if not running:
                    break
                time.sleep(1)
    finally:
        if registered:
            try:
                notify(args.network, args.interface, {}, up=False)
            except (OSError, subprocess.SubprocessError):
                pass


if __name__ == '__main__':
    main()
