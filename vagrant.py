#!/usr/bin/env python
"""\
Dynamic inventory for Vagrant - parse the output of `vagrant ssh-config` and
generate an inventory based on that.
"""
from __future__ import absolute_import
from __future__ import unicode_literals, print_function, division
import argparse                          # cli
import os                                # path
from sys import exit                     # exiting early on error
import re                                # role decisions
import subprocess                        # output from `vagrant-ssh`
import parsimonious                      # parsing said output
from parsimonious.nodes import RegexNode # generic visit/parse for regexes
import json                              # dumping parsed output to inventory
import logging                           # log errors to file w/o printing them

# To log during testing, this must be configured outside __main__
logging.basicConfig(filename="vagrant.py.log", level=logging.INFO,
        filemode="w")

VERSION = '0.1pre'

### PARSING ###

class Walker(parsimonious.NodeVisitor):
    """ This class will traverse the parsimonious parse tree, depth-first.

    The argument child_results contains a list of the results of parsing all
    the child nodes of the current one (node). It is often unpacked to ignore
    whitespace, etc.
    """
    def __init__(self, grammar):
        """ Give this Walker a default parsing grammar """
        self.grammar = grammar

    def generic_visit(self, node, children):
        """ This method is called when no other applies (e.g. whitespace).

        For subclasses of RegexNode, it just returns their match.

        For anything else, it returns its own children (because hard to debug
        general generic nodes without names can shadow important ones, e.g.
        arbitrary_line). See https://github.com/erikrose/parsimonious/issues/59.

        Additionally, this behavior replaces a top level visit_output that would
        just return its own children and a visit_line that would return its
        first child.
        """
        if isinstance(node, RegexNode):
            logging.debug("visiting regex node " +  node.expr_name)
            return node.match.group(0)
        else:
            logging.debug("visiting generic node " +  node.expr_name + " : "
                    + repr(node.text))
            return children

    def visit_block(self, node, child_results):
        """ Collect the results (k/v pairs) from each line into a dict """
        logging.debug("visiting some block")
        (_, first_line, rest_lines, last_line) = child_results
        # The lines+ are returned as [[(key, value)],...], so we flatten them
        flattened_rest = [item for sublist in rest_lines for item in sublist]
        # If the last line was a match, include its result
        if len(last_line) > 0 and len(last_line[0]) == 2:
            lst = [first_line] + flattened_rest + [last_line[0]]
        else:
            lst = [first_line] + flattened_rest
        return {k: v for (k, v) in lst }

    def visit_first_line(self, node, child_results):
        """ Just take the key and value from the first line """
        logging.debug("visiting first line: " + node.text.strip())
        (key, _, value, _) = child_results
        return (key, value)

    def visit_last_line(self, node, child_results):
        """ Last line might not be followed by a newline """
        logging.debug("visiting last line: " + node.text.strip())
        (_, key, _, value) = child_results
        return (key, value)

    def visit_port_line(self, node, child_results):
        """ Actually parse the port as an int. """
        return self.visit_arbitrary_line(node, child_results)

    def visit_arbitrary_line(self, node, child_results):
        logging.debug("visiting arbitrary line: " + node.text.strip())
        logging.debug("Child results of line: " + repr(child_results))
        (_, key, _, value, _) = child_results
        return (key, value)

    def visit_port_number(self, node, child_results):
        logging.debug("visiting port number: " + node.text.strip())
        try:
            return int(node.match.group(0))
        except ValueError:
            # This should never happen, and might indicate a bug in parsimonious
            # The "[0-9]" regex should take care of any non-integer string.
            logging.warning("Couldn't parse port, removing line: " + node.text)

def get_host_dicts(full_text):
    """ Return a list of dictionaries representing vagrant VMs (hosts).
    These dictionaries have keys defined by the first word in a line, and values
    that are the rest of that line, e.g.
    `{ "Host": "control", "Hostname": "127.0.0.1", "Port": 2200, ... }`.
    Appropriate fields will be parsed as their native types, specifically "Port"
    will be parsed as an int.
    """
    # Parsimonious grammar, similar to BNF:
    # https://github.com/erikrose/parsimonious
    return Walker(parsimonious.Grammar(r"""
      output         = block+
      block          = newline* first_line line+ last_line?
      line           = port_line / arbitrary_line
      # Only the first line is unindented
      first_line     = key             whitespace1 hostname    newline
      port_line      = whitespace2 key whitespace1 port_number newline
      arbitrary_line = whitespace2 key whitespace1 value       newline
      # last_line only gets called when the last line has no trailing newline,
      # e.g. it won't be called if there's another block following.
      last_line      = whitespace2 key whitespace1 value
      key            = ~"[A-z]+"
      # Values are arbitrary and can be paths, ints, etc.
      value          = ~".+"
      newline        = ~"\n"
      whitespace1    = ~"\s"
      whitespace2    = ~"\s\s"
      # https://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names
      hostname       = ~"[A-z0-9-]+"i
      # Port numbers are in the range 1~65000
      port_number    = ~"[0-9]{1,5}"
    """)).match(full_text)

def ssh_config_output(work_dir):
    """ Just get the output of `vagrant ssh-config` as a str """
    args = ["vagrant", "ssh-config"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=work_dir)
    stdout, stderr = map(lambda x: x.decode("utf-8"), proc.communicate())
    proc.wait()
    # Log errors, return empty string
    if proc.returncode != 0:
        msg = "Error: " + str(proc.args) + " exited with non-zero exit code "
        logging.fatal(msg + str(proc.returncode))
        logging.fatal("stdout: " + stdout)
        logging.fatal("stderr: " + stderr)
        exit(1)
    return stdout

### INVENTORY CONSTRUCTION ###

def get_role(host_dict):
    """ Return "control", "worker", or "" depending on regex match """
    hostname = host_dict["Host"]
    if re.match(r"control-\d\d", hostname):
        return "control"
    elif re.match(r"worker-\d\d\d", hostname):
        return "worker"
    return ""

def get_groups(host_dicts):
    """ Return a dictionary of groups, with keys being group names and values
    being lists of hostnames in that group """
    role_control = []
    role_worker  = []
    dc_vagrantdc = []
    for host_dict in host_dicts:
        hostname = host_dict["Host"]
        role = get_role(host_dict)
        dc_vagrantdc.append(hostname)
        if role == "control":
            role_control.append(hostname)
        elif role == "worker":
            role_worker.append(hostname)
    return {
        "role=control": role_control,
        "role=worker": role_worker,
        "dc=vagrantdc": dc_vagrantdc
    }

def generic_hostvars(host_dict):
    """ Return a dictionary of generic host variables to be listed under this
    host in the `_meta` section. """
    return {
        "ansible_ssh_user": "vagrant",
        "ansible_ssh_port": host_dict["Port"],
        "ansible_ssh_host": host_dict["HostName"]
    }

def mantl_hostvars(host_dict):
    """ Return a dictionary of mantl-specific host variables to be listed under
    this host in the `_meta` section. """
    ip = host_dict["HostName"]
    role = get_role(host_dict)
    return {
        "public_ipv4": ip,
        "private_ipv4": ip,
        "role": role,
        "consul_is_server": role == "control",
    }

def group_hostvars(host_dict, groups):
    """ Return a dictionary of host variables that can be deduced from the
    groups that this host belongs to """
    if host_dict["Host"] in groups.get("dc=vagrantdc"):
        return {
            "consul_dc": "vagrantdc",
            "publicly_routable": True,
            "provider": "virtualbox",
        }
    return {}

def inventory(host_dicts, mantl_specific=False):
    """ Construct a dictionary representing a valid Ansible inventory """
    def merge_dicts(*dict_args):
        """ Combine multiple dictionaries into one """
        result = {}
        for dictionary in dict_args:
            result.update(dictionary)
        return result

    # Get the groups in inventory format, with a "hosts" list
    groups = get_groups(host_dicts)
    groups_json = { grp : { "hosts" : hs } for (grp, hs) in groups.items() }

    # Keys are hostnames, values are all their variables
    hostvars = [ (d, generic_hostvars(d)) for d in host_dicts ]
    # Add mantl-specific variables if requested
    if mantl_specific:
        for (host_dict, vs) in hostvars:
            vs.update(mantl_hostvars(host_dict))
            vs.update(group_hostvars(host_dict, groups))
    hostvars_json = { d["Host"]: vs for (d, vs) in hostvars }

    # Merge groups dictionary with properly formatted hostvars dictionary
    #hostvars_dict = { hostname : vrs for (hostname, vrs) in hostvars.items() }
    return merge_dicts(groups_json, { "_meta": { "hostvars": hostvars_json } })

### EXECUTING ###

def main():
    parser = argparse.ArgumentParser(__file__, __doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--list',
                       action='store_true',
                       default=True,
                       help='list all variables')
    modes.add_argument('--host', help='list variables for a single host')
    modes.add_argument('--version',
                       action='store_true',
                       help='print version and exit')
    parser.add_argument('--pretty',
                        action='store_true',
                        help='pretty-print output JSON')
    parser.add_argument('--nometa',
                        action='store_true',
                        help='with --list, exclude hostvars')
    parser.add_argument('--root',
                        default=os.path.dirname(os.path.abspath(__file__)),
                        help='custom root to run for `vagrant ssh-config` in')
    args = parser.parse_args()

    if args.version:
        print('%s %s' % (__file__, VERSION))
    elif args.list:
        iv = inventory(get_host_dicts(ssh_config_output(args.root)),
                mantl_specific=True)
        if args.nometa:
            del iv['_meta']
        print(json.dumps(iv, indent=4 if args.pretty else None))
    elif args.host:
        hosts = get_host_dicts(ssh_config_output(args.root))
        for host in hosts:
            if host["Host"] == args.host:
                hostvars = generic_hostvars(host)
                hostvars.update(mantl_hostvars(host))\
                        .update(group_hostvars(host))
                print(json.dumps(hostvars, indent=4 if args.pretty else None))
    else:
        print("Please specify either --list or --host")
    parser.exit()

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        pass
    except:
        err_msg = """Recieved an unhandled exception in main method. This is
        always an error, please report it to the Github issue tracker. """
        logging.exception(err_msg)
        raise
