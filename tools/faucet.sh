#!/usr/bin/env bash
# Swap Base Sepolia SepETH for Lasna lREACT using Reactive's faucet contract.
# Rate: 1 ETH = 100 lREACT. Do not send more than 5 ETH in one transaction.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"

BASE_RPC="https://sepolia.base.org"
FAUCET_BASE_SEPOLIA="0x2afaFD298b23b62760711756088F75B7409f5967"
AMOUNT="${1:-0.004ether}"

set -a; source .env; set +a

echo "burner:    $DEPLOYER"
echo "base eth:  $(cast balance "$DEPLOYER" --rpc-url "$BASE_RPC" --ether)"
echo "lasna:     $(cast balance "$DEPLOYER" --rpc-url https://lasna-rpc.rnk.dev/ --ether)"

cast send "$FAUCET_BASE_SEPOLIA" "request(address)" "$DEPLOYER" \
  --value "$AMOUNT" --rpc-url "$BASE_RPC" --private-key "$PRIVATE_KEY"

sleep 15
echo "lasna after: $(cast balance "$DEPLOYER" --rpc-url https://lasna-rpc.rnk.dev/ --ether)"
