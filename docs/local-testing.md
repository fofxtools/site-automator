# Local Testing

Docker and LXD containers can be used for local testing. LXD is used as WordOps is not Docker friendly.

Note that `.localhost` domains are a special case and intercept `/etc/hosts`. Thus `.test` extensions are advised.

## Docker containers

See: [../dev/Dockerfile.caddy](../dev/Dockerfile.caddy)

Build the container with Caddy and Hugo:

```bash
cd dev

docker build -f Dockerfile.caddy \
  --build-arg SSH_PUBLIC_KEY="$(cat ~/.ssh/id_ed25519.pub)" \
  -t site-automator-caddy-test .

docker rm -f automator-caddy 2>/dev/null || true

docker run -d -p 22:22 -p 8080:80 --name automator-caddy site-automator-caddy-test
```

Add to `~/.ssh/config` to add the server alias, and to suppress key verification prompts for localhost:

```bash
Host automator-caddy
  HostName localhost
  User root
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
  ServerAliveInterval 60
  ServerAliveCountMax 10

Host localhost
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
```

To connect:

```bash
ssh automator-caddy
```

## LXD containers

From the host (outside the container):

```bash
# Initialize LXD
snap install lxd
sudo usermod -aG lxd $USER
newgrp lxd
lxd init

# Check the assigned subnet
# Look for the IPv4 address, e.g. 10.x.x.1/24
SUBNET=$(lxc network show lxdbr0 | grep 'ipv4.address' | awk '{print $2}' | sed 's|\.[0-9]*/|.0/|')

# Fix LXD networking (Docker's FORWARD DROP policy blocks LXD traffic)
sudo iptables -t nat -A POSTROUTING -s $SUBNET ! -d $SUBNET -j MASQUERADE
sudo iptables -I FORWARD -s $SUBNET -j ACCEPT
sudo iptables -I FORWARD -d $SUBNET -j ACCEPT
sudo apt install iptables-persistent
sudo netfilter-persistent save

# Launch container
lxc launch ubuntu:24.04 automator-wordops
lxc exec automator-wordops -- cloud-init status --wait
lxc file push ~/.ssh/id_ed25519.pub automator-wordops/tmp/host_key.pub
lxc exec automator-wordops -- bash
```

Inside the container:

```bash
apt update && apt upgrade -y && apt install -y openssh-server rsync cron curl wget gnupg2 ca-certificates lsb-release software-properties-common

mkdir -p /root/.ssh

cat /tmp/host_key.pub >> /root/.ssh/authorized_keys

chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys

wget -qO wo wops.cc && sudo bash wo

exit
```

Host (re-enter after installer modifies PATH):

```bash
lxc exec automator-wordops -- bash
```

Inside container:

```bash
wo stack install
exit
```

Host:

```bash
lxc snapshot automator-wordops post-wordops
lxc list automator-wordops
```

Then based on the IP from `lxc list automator-wordops`, add to `~/.ssh/config`:

```bash
Host automator-wordops
    HostName <container-ip>
    User root
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ServerAliveInterval 60
    ServerAliveCountMax 10
```

Then add site to `/etc/hosts` based on the IP from `lxc list automator-wordops`:

```bash
<container-ip> <domain>
```