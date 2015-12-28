#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import unicode_literals, print_function, division
import vagrant  # module we're testing
import unittest # testing/debugging utilities
import pprint
import re
import os

mantl_worker_block = """\nHost worker-001
  HostName 127.0.0.1
  User vagrant
  Port 2222
  UserKnownHostsFile /dev/null
  StrictHostKeyChecking no
  PasswordAuthentication no
  IdentityFile /home/siddharthist/Dropbox/code/asteris/microservices-infrastructure/.vagrant/machines/worker/virtualbox/private_key
  IdentitiesOnly yes
  LogLevel FATAL"""
mantl_control_block = """Host control-01
  HostName 127.0.0.1
  User vagrant
  Port 2200
  UserKnownHostsFile /dev/null
  StrictHostKeyChecking no
  PasswordAuthentication no
  IdentityFile /home/siddharthist/Dropbox/code/asteris/microservices-infrastructure/.vagrant/machines/control/virtualbox/private_key
  IdentitiesOnly yes
  LogLevel FATAL"""

mantl_example_blocks = [ mantl_worker_block, mantl_control_block ]

# These are the expected parsed dictionaries from the above text blocks
mantl_worker_dict = {
    'Host': 'worker-001',
    'HostName': '127.0.0.1',
    'IdentitiesOnly': 'yes',
    'IdentityFile':
    '/home/siddharthist/Dropbox/code/asteris/microservices-infrastructure/.vagrant/machines/worker/virtualbox/private_key',
    'LogLevel': 'FATAL',
    'PasswordAuthentication': 'no',
    'Port': 2222,
    'StrictHostKeyChecking': 'no',
    'User': 'vagrant',
    'UserKnownHostsFile': '/dev/null'
}
mantl_control_dict = {
    'Host': 'control-01',
    'HostName': '127.0.0.1',
    'IdentitiesOnly': 'yes',
    'IdentityFile':
    '/home/siddharthist/Dropbox/code/asteris/microservices-infrastructure/.vagrant/machines/control/virtualbox/private_key',
    'LogLevel': 'FATAL',
    'PasswordAuthentication': 'no',
    'Port': 2200,
    'StrictHostKeyChecking': 'no',
    'User': 'vagrant',
    'UserKnownHostsFile': '/dev/null'
}
mantl_host_dicts = [ mantl_worker_dict, mantl_control_dict ]

pp = pprint.PrettyPrinter(indent=4)
debug = False

class TestParsingFunctions(unittest.TestCase):
    def test_get_host_dicts(self):
        expected_worker = mantl_worker_dict
        actual_worker   = vagrant.get_host_dicts(mantl_worker_block)[0]
        if debug:
            pp.pprint(expected_worker)
            pp.pprint(actual_worker)
        self.assertEqual(expected_worker, actual_worker)

        expected_control = mantl_control_dict
        actual_control   = vagrant.get_host_dicts(mantl_control_block)[0]
        if debug:
            pp.pprint(expected_control)
            pp.pprint(actual_control)
        self.assertEqual(expected_control, actual_control)

        expected  = mantl_host_dicts
        actual    = vagrant.get_host_dicts("\n\n".join(mantl_example_blocks))
        if debug:
            pp.pprint(expected)
            pp.pprint(actual)
        self.assertEqual(expected, actual)

class TestInventoryFunctions(unittest.TestCase):
    def test_get_role(self):
        self.assertEqual("worker", vagrant.get_role(mantl_worker_dict))
        self.assertEqual("control", vagrant.get_role(mantl_control_dict))
        self.assertEqual("", vagrant.get_role({"Host": "testfail"}))

    def test_get_groups(self):
        expected = {
            "role=control": ["control-01"],
            "role=worker": ["worker-001"],
            "dc=vagrantdc": ["worker-001", "control-01"]
        }
        self.assertEqual(expected, vagrant.get_groups(mantl_host_dicts))

    def test_generic_hostvars(self):
        expected = {
            "ansible_ssh_host": "127.0.0.1",
            "ansible_ssh_port": 2222,
            "ansible_ssh_user": "vagrant"
        }
        self.assertEqual(expected, vagrant.generic_hostvars(mantl_worker_dict))

    def test_mantl_hostvars(self):
        expected = {
            "public_ipv4": "127.0.0.1",
            "private_ipv4": "127.0.0.1",
            "role": "worker",
            "consul_is_server": False
        }
        self.assertEqual(expected, vagrant.mantl_hostvars(mantl_worker_dict))

    def test_ssh_config_output(self):
        with self.assertRaises(Exception):
            path = os.path.dirname(os.path.abspath(__file__))
            vagrant.ssh_config_output(path)

if __name__ == '__main__':
    unittest.main()
