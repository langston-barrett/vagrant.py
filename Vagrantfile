# -*- mode: ruby -*-
# vi: set ft=ruby :
require 'yaml'

# Public key to copy into VMs' authorized_keys file (for use with Ansible)
PUBLIC_KEY = "#{Dir.home}/.ssh/id_rsa.pub"
# How many hosts would you like to test with?
VMS = 2

Vagrant.configure(2) do |config|
  config.vm.provider "virtualbox"
  config.vm.provider "vmware_fusion"
  config.vm.box = "centos/7"
  # These VMs aren't doing anything, they don't need many resources
  config.vm.provider :virtualbox do |vb|
    vb.customize ['modifyvm', :id, '--cpus', 1]
    vb.customize ['modifyvm', :id, '--memory', 512]
  end

  # No need to sync any folders
  config.vm.synced_folder '.', '/vagrant', disabled: true
  config.vm.synced_folder '.', '/home/vagrant/sync', disabled: true

  # Try as many as you want! Just change the second int here.
  (1..VMS).each do |i|
    config.vm.define "node-#{i}" do |node|
      node.vm.hostname = "node-#{i}"
      node.vm.network "private_network", :ip => "192.100.100.1#{i}"

      # Copy host's public key (see above, circa line 5)
      ssh_pub_key = File.readlines(PUBLIC_KEY).first.strip
      node.vm.provision "shell", inline: <<-EOF
        echo '#{ssh_pub_key}' >> /home/vagrant/.ssh/authorized_keys
      EOF

      # Only call vagrant.py after the last host is up. Otherwise, `vagrant
      # ssh-config` will report that some hosts aren't ready.
      if i >= VMS
        node.vm.provision "ansible" do |ansible|
          ansible.playbook       = "example_playbook.yml"
          ansible.inventory_path = "vagrant.py"
        end
      end
    end
  end
end
