#!/usr/bin/env python3
"""Host tests; no root, ubus, alfred daemon or route changes required."""
import importlib.util
import ipaddress as ip
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('routes', Path(__file__).parent / 'files/edgez-subnet-routes.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
OWNER = 'b4:3a:45:a4:56:74'


def sample(seq=1, ttl=45, boot='00000001', subnet='10.87.212.128/27', hop='10.42.0.23'):
    return m.records(f'{{ "{OWNER}", "EZ4R1 {boot} {seq:08x} {subnet} {hop} {ttl}" }},')


def gateway_sample(owner=OWNER, seq=1, ttl=45, boot='00000001', hop='10.42.0.1',
                   down=100000, up=100000, load=0):
    return m.gateway_records(
        f'{{ "{owner}", "EZGW1 {boot} {seq:08x} {hop} {down} {up} {load} {ttl}" }},')


class Routes(unittest.TestCase):
    def test_wire(self):
        self.assertIn(OWNER, sample())
        self.assertFalse(sample(subnet='10.42.0.0/27'))
        self.assertFalse(sample(subnet='10.70.0.0/27'))
        self.assertFalse(sample(subnet='10.87.212.129/27'))
        self.assertFalse(sample(subnet='0.0.0.0/0'))
        self.assertFalse(sample(hop='127.0.0.1'))
        self.assertFalse(m.records('{"'+OWNER+'", "EZ6D"},'))

    def test_gateway_wire_and_ranking(self):
        self.assertIn(OWNER, gateway_sample())
        self.assertFalse(gateway_sample(hop='127.0.0.1'))
        self.assertFalse(gateway_sample(load=101))
        addresses = [{'addr_info': [{'family': 'inet', 'local': '10.42.0.23', 'prefixlen': 24}]}]
        other = '02:00:00:00:00:02'
        active = gateway_sample()
        active.update(gateway_sample(owner=other, hop='10.42.0.2'))
        first = m.rank_gateways(active, addresses, 'node-a')
        self.assertEqual({(owner, hop) for _, owner, hop in first},
                         {(OWNER, '10.42.0.1'), (other, '10.42.0.2')})
        self.assertEqual(first, m.rank_gateways(active, addresses, 'node-a'))
        self.assertFalse(m.rank_gateways(gateway_sample(hop='10.43.0.1'), addresses, 'node-a'))
        only_other = m.rank_gateways(active, addresses, 'node-a', {other: 200})
        self.assertEqual([(owner, hop) for _, owner, hop in only_other],
                         [(other, '10.42.0.2')])

    def test_gateway_quality_and_hysteresis(self):
        output = '[{"orig_address":"aa:bb:cc:dd:ee:ff","tq":255}]'
        with patch.object(m, 'run', return_value=output):
            self.assertEqual(m.batman_gateway_quality(), {'aa:bb:cc:dd:ee:ff': 255})
        translation = ('[{"orig_address":"aa:bb:cc:dd:ee:ff",'
                       '"tt_address":"02:00:00:00:00:02","best":true}]')
        with patch.object(m, 'run', return_value=translation):
            origins = m.batman_client_origins()
        self.assertEqual(origins, {'02:00:00:00:00:02': 'aa:bb:cc:dd:ee:ff'})
        self.assertEqual(
            m.correlate_gateway_quality(
                {'02:00:00:00:00:02': ()}, {'aa:bb:cc:dd:ee:ff': 255}, origins),
            {'02:00:00:00:00:02': 255})
        selector = m.GatewaySelector(improvement=1.2, hold_seconds=10)
        first = [(100, OWNER, '10.42.0.1'), (90, '02:00:00:00:00:02', '10.42.0.2')]
        self.assertEqual(selector.update(first, 0), '10.42.0.1')
        better = [(130, '02:00:00:00:00:02', '10.42.0.2'), (100, OWNER, '10.42.0.1')]
        self.assertEqual(selector.update(better, 5), '10.42.0.1')
        self.assertEqual(selector.update(better, 10), '10.42.0.2')
        self.assertEqual(selector.update([(100, OWNER, '10.42.0.1')], 11), '10.42.0.1')

    def test_gateway_uses_mesh_default_only_as_wan_fallback(self):
        self.assertTrue(m.use_mesh_default(True, False, False))
        self.assertFalse(m.use_mesh_default(False, True, True))
        self.assertTrue(m.use_mesh_default(False, True, False))

    def test_topology_status_contains_subnet_and_gateway_marker(self):
        gateways = gateway_sample(hop='10.42.0.23')
        snapshot = m.status_snapshot(
            sample(), gateways, gateways, {OWNER: 'aa:bb:cc:dd:ee:ff'},
            local_prefix=ip.IPv4Network('10.80.1.0/27'), gateway_mode=True,
            local_wan_ready=True, now=123)
        self.assertEqual(snapshot['updated_at'], 123)
        self.assertEqual(snapshot['local'], {
            'gateway_role': True,
            'internet_gateway': True,
            'wifi_subnet': '10.80.1.0/27',
        })
        self.assertEqual(snapshot['nodes'][OWNER], {
            'wifi_subnet': '10.87.212.128/27',
            'transit_ip': '10.42.0.23',
            'gateway_role': True,
            'internet_gateway': True,
            'mesh_mac': 'aa:bb:cc:dd:ee:ff',
        })

        offline = m.status_snapshot(sample(), {}, gateways, now=124)
        self.assertTrue(offline['nodes'][OWNER]['gateway_role'])
        self.assertNotIn('internet_gateway', offline['nodes'][OWNER])

    def test_expiry_cached_replay_reboot_and_withdrawal(self):
        f = m.Freshness()
        self.assertFalse(f.update(sample(), 0))
        self.assertTrue(f.update(sample(2), 10))
        self.assertTrue(f.update(sample(2), 54))
        self.assertFalse(f.update(sample(2), 55))
        self.assertFalse(f.update(sample(1), 56))
        self.assertFalse(f.update(sample(3, ttl=0), 57))
        self.assertIn(OWNER, f.recent(57))
        self.assertNotIn(OWNER, f.recent(102))
        self.assertFalse(f.update(sample(1, boot='00000002'), 58))
        self.assertTrue(f.update(sample(2, boot='00000002'), 68))

    def test_each_publisher_start_gets_a_new_session(self):
        with patch.object(m.uuid, 'uuid4', side_effect=[
                m.uuid.UUID('11111111-0000-0000-0000-000000000000'),
                m.uuid.UUID('22222222-0000-0000-0000-000000000000')]):
            self.assertEqual(m.session_id(), '11111111')
            self.assertEqual(m.session_id(), '22222222')

    def test_routes_and_conflicts(self):
        addresses = [{'addr_info': [{'family': 'inet', 'local': '10.42.0.1', 'prefixlen': 24}]}]
        leases = {(OWNER, ip.IPv4Address('10.42.0.23'))}
        active = sample()
        expected = {'10.87.212.128/27': '10.42.0.23'}
        self.assertEqual(m.desired_routes(active, addresses, [], leases), expected)
        self.assertFalse(m.desired_routes(active, addresses, [], set()))
        self.assertFalse(m.desired_routes(sample(hop='10.43.0.23'), addresses, [], None))
        self.assertFalse(m.desired_routes(sample(hop='10.42.0.1'), addresses, [], None))
        self.assertFalse(m.desired_routes(sample(hop='10.42.0.255'), addresses, [], None))
        other = {'dst': '10.87.212.0/24', 'gateway': '10.42.0.2'}
        self.assertFalse(m.desired_routes(active, addresses, [other], leases))
        ours = {'dst': '10.87.212.128/27', 'gateway': '10.42.0.23'}
        self.assertEqual(m.desired_routes(active, addresses, [ours], leases, expected), expected)
        active['02:00:00:00:00:02'] = active[OWNER]
        self.assertFalse(m.desired_routes(active, addresses, [], leases))

    def test_netifd_owns_routes(self):
        import json
        with patch.object(m, 'run') as run:
            m.notify('edgez_routes', 'br-ahwlan', {'10.87.212.128/27': '10.42.0.23'})
            args = run.call_args.args
            self.assertEqual(args[:4], ('ubus', 'call', 'network.interface', 'notify_proto'))
            data = json.loads(args[4])
            self.assertEqual(data['interface'], 'edgez_routes')
            self.assertFalse(data['keep'])
            self.assertEqual(data['routes'], [{'target': '10.87.212.128', 'netmask': '27', 'gateway': '10.42.0.23'}])

            m.notify('edgez_routes', 'br-ahwlan', {}, '10.42.0.1')
            data = json.loads(run.call_args.args[4])
            self.assertEqual(data['routes'], [
                {'target': '0.0.0.0', 'netmask': '0', 'gateway': '10.42.0.1'}])
            m.notify('edgez_routes', 'br-ahwlan', {}, up=False)
            self.assertFalse(json.loads(run.call_args.args[4])['link-up'])

    def test_interface_addresses(self):
        output = '[{"addr_info":[{"family":"inet","local":"10.41.0.1","prefixlen":16}]}]'
        with patch.object(m, 'run', return_value=output) as run:
            self.assertEqual(m.interface_addresses('br-ahwlan')[0]['addr_info'][0]['local'],
                             '10.41.0.1')
            run.assert_called_once_with('ip', '-j', '-4', 'address', 'show', 'dev',
                                        'br-ahwlan')


if __name__ == '__main__':
    unittest.main()
