# vagrant.py

**Table of Contents**
- [vagrant.py](#vagrantpy)
    - [Disclaimer](#disclaimer)
    - [Installation](#installation)
    - [Usage](#usage)
    - [Gotchas](#gotchas)
    - [License](#license)

`vagrant.py` is a dynamic Ansible inventory script to connect to systems by
reading the output of Vagrant's `vagrant ssh-config` command.

## Disclaimer

You might not need this. Vagrant 1.8 includes an `ansible_local` provisioner
with options that make this somewhat obsolete. You can check out an example of
how that's used in [Mantl](https://github.com/CiscoCloud/microservices-infrastructure/blob/master/Vagrantfile).

## Installation

Just put `vagrant.py` somewhere convenient and run
`pip install -r requirements.txt` to grab all the required libraries.

## Usage

### From the command line on the host

First, make sure that your Vagrant instances are up and ready for SSH.

Next, specify `vagrant.py` as an inventory source for any Ansible command. For
instance, to use this to test if your servers are working:
```bash
ansible all -m ping -i vagrant.py
```

Or in a playbook:
```bash
ansible-playbook -i vagrant.py your_playbook.yml
```
See the "Gotchas" section if these examples doesn't work for you.

### From your Vagrantfile

You can also use vagrant.py directly from Vagrant's ansible provisioner. See the
provided Vagrantfile for an example.

## Variables

vagrant.py fills in some helpful Ansible variables for each host:
 * ansible\_ssh\_user - "vagrant"
 * ansible\_ssh\_host - each VM's IP address or hostname
 * ansible\_ssh\_port - each VM's preferred SSH port

## Mantl-specific variables

As this project was developed for use with [Mantl](http://mantl.io/), it
attaches a few extra host variables which you can safely use or ignore. They
are:
 * public\_ipv4 - each VM's IP address
 * private\_ipv4 - each VM's IP address
 * role=(control | worker)
   - hosts are assigned the control role if their hostnames match the regex
   "control-\d\d"
   - the worker role works similarly for the regex "worker-\d\d\d"
 * consul\_is\_server - true if role == "control", false otherwise

And it attaches the follow groups and respective host variables:
 * dc=vagrantdc
   - consul\_dc="vagrantdc"
   - publicly\_routable=true
   - provider=virtualbox

## Gotchas

Ansible might fail to SSH into the machine for any number of reasons, but here
are a few common ones:
 * The VM is not ready for SSH access
 * The preferred username is not "vagrant"
 * The private key isn't part of the hosts' `~/.ssh/authorized_keys` file
 * Ansible is using the wrong private key. You can set it like this:
```bash
ansible all -m ping -i vagrant.py --private-key=$HOME/.ssh/id_rsa
```
 * The private key has a password, but `--ask-pass` wasn't used, e.g.
```bash
ansible all -m ping -i vagrant.py --ask-pass
```
 * Strict host key checking is enabled, and you've build multiple VMs at that
 IP address with different host keys
