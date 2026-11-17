#!/usr/bin/env bash
# Waits for Base Sepolia ETH to land on the burner, then runs the whole loop unattended.
# Logs to auto.log. Exits non-zero after 12 hours with nothing to do.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"
set -a; source .env; set +a

BASE_RPC="https://sepolia.base.org"
MIN_WEI=3000000000000000   # 0.003 ETH, enough for 3 deploys, a faucet swap and a ping

echo "[auto] $(date -u +%FT%TZ) waiting for Base Sepolia ETH on $DEPLOYER"
deadline=$(( $(date +%s) + 12*3600 ))
while :; do
  wei=$(cast balance "$DEPLOYER" --rpc-url "$BASE_RPC")
  if [ "$wei" -ge "$MIN_WEI" ]; then
    echo "[auto] funded: $wei wei"
    break
  fi
  l1=$(cast balance "$DEPLOYER" --rpc-url https://ethereum-rpc.publicnode.com 2>/dev/null || echo 0)
  if [ "${l1:-0}" -gt 0 ] 2>/dev/null; then
    echo "[auto] WARNING: $l1 wei sits on Ethereum mainnet, this loop only counts Base Sepolia"
  fi
  if [ "$(date +%s)" -gt "$deadline" ]; then
    echo "[auto] gave up waiting after 12h"
    exit 2
  fi
  sleep 30
done

echo "[auto] swapping for lREACT"
./tools/faucet.sh 0.004ether || echo "[auto] faucet swap failed, trying with what is there"

echo "[auto] running the loop"
python3 tools/loop.py
status=$?
echo "[auto] loop exit: $status"
exit $status
