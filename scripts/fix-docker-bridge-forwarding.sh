#!/usr/bin/env bash
# Some cloud agent / nested-VM hosts only wire iptables-legacy for docker0.
# Compose project bridges (br-*) then drop inter-container traffic. This script
# allows forwarding for all Docker bridge interfaces via DOCKER-USER.
set -euo pipefail
if command -v iptables-legacy >/dev/null 2>&1; then
  IPT=iptables-legacy
elif command -v iptables >/dev/null 2>&1; then
  IPT=iptables
else
  echo "iptables not found; skipping"
  exit 0
fi
if ! sudo -n true 2>/dev/null; then
  echo "sudo required to adjust Docker bridge forwarding"
  exit 1
fi
sudo "$IPT" -C DOCKER-USER -i br-+ -j ACCEPT 2>/dev/null || sudo "$IPT" -I DOCKER-USER -i br-+ -j ACCEPT
sudo "$IPT" -C DOCKER-USER -o br-+ -j ACCEPT 2>/dev/null || sudo "$IPT" -I DOCKER-USER -o br-+ -j ACCEPT
echo "DOCKER-USER rules ensured for br-+ interfaces"
