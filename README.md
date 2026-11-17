# Reactive Omni spike: full-loop latency

Throwaway spike for the Reactive Omni Buildathon. It answers one question before any product
gets built: **how long does one event take to travel origin chain -> Reactive Lasna -> callback
back to the origin chain, measured on real testnets?**

## What is in here

| File | Role |
|---|---|
| `src/PingOrigin.sol` | Origin contract on Base Sepolia. `ping(nonce)` emits `Ping(sender, nonce, sentAt, pingBlock)` |
| `src/PingReactive.sol` | Reactive contract on Lasna. Subscribes to `Ping`, rebuilds the payload in `react()`, emits `Callback` |
| `src/PongSink.sol` | Destination contract on Base Sepolia. Accepts the callback from the callback proxy and records arrival time and block |
| `test/Loop.t.sol` | 4 tests: origin event shape, payload layout (`address(0)` first slot for RVM ID injection), sink auth, stranger rejected |
| `tools/newkey.py` | Generates the burner key into `.env` without printing it |
| `tools/faucet.sh` | Swaps Base Sepolia ETH for Lasna lREACT through Reactive's faucet contract |
| `tools/loop.py` | Deploys the three contracts, funds the reactive contract, fires one ping, polls for the callback, writes `results.json` |

## Verified so far

- Lasna (5318007), Base Sepolia (84532), Unichain Sepolia (1301) all producing blocks
- Reactive system contract live on Lasna at `0x8888...8888`, callback proxy live on Base Sepolia at `0x476F44b1...3585`
- Reactive faucet contract live on Base Sepolia at `0x2afaFD29...5967` (rate 1 ETH = 100 lREACT)
- `forge build` clean, `forge test` 4/4 pass

## Pending: testnet funds

The reactive contract needs lREACT for event delivery and callback gas, and the deployer needs
Base Sepolia ETH for three deploys plus the faucet swap. Both come from the same deposit, because
Reactive's faucet lives on Base Sepolia.

```bash
# 1. send Base Sepolia ETH to the burner address in .env (DEPLOYER)
# 2. swap part of it for lREACT
./tools/faucet.sh 0.02ether
# 3. run the loop and write results.json
python3 tools/loop.py
```

`results.json` records the ping block, the callback block, the timestamp delta, the Base Sepolia
block delta (200 ms blocks, so sub-second resolution), and the wall clock for the whole run.
