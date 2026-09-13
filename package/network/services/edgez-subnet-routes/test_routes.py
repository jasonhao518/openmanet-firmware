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


class Routes(unittest.TestCase):
    def test_wire(self):
        self.assertIn(OWNER, sample())
        self.assertFalse(sample(subnet='10.42.0.0/27'))
        self.assertFalse(sample(subnet='10.87.212.129/27'))
        self.assertFalse(sample(subnet='0.0.0.0/0'))
        self.assertFalse(sample(hop='127.0.0.1'))
        self.assertFalse(m.records('{"'+OWNER+'", "EZ6D"},'))

    def test_expiry_cached_replay_reboot_and_withdrawal(self):
        f = m.Freshness()
        self.assertFalse(f.update(sample(), 0))
        self.assertTrue(f.update(sample(2), 10))
        self.assertTrue(f.update(sample(2), 54))
        self.assertFalse(f.update(sample(2), 55))
        self.assertFalse(f.update(sample(1), 56))
        self.assertFalse(f.update(sample(3, ttl=0), 57))
        self.assertFalse(f.update(sample(1, boot='00000002'), 58))
        self.assertTrue(f.update(sample(2, boot='00000002'), 68))

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
