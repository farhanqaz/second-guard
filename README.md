# Reactive Omni spike: full-loop latency

Throwaway spike for the Reactive Omni Buildathon. Two questions, both answered with live testnets:

1. How long does one event take to travel origin chain -> Reactive Lasna -> callback back? (the latency spike)
2. Can a reactive contract watch the same pair on two chains and stop both venues when they diverge? (the product)

## Product result: cross-venue divergence guard, live

One dump on the Base Sepolia venue moved its price 32%. The guard saw both feeds, computed 2753 bps of
divergence, and paused both venues through two separate callbacks in the same second.

| Evidence | Value |
|---|---|
| Attack tx (Base Sepolia) | `0xa0714e02fdb50b2a17314975378fb46b1fc01a2fe3d5b2d7cc3f40d688da5b0b` at block 59901740 |
| Base pause callback | `0x9fcf78f1b779c31d21552dff340bc9cf5ac739e89648e6fd017f41a5e81bf544` block 59901746 |
| Unichain pause callback | `0xd9cfb89baaaab0a8bd3ba03879105b00f7e471a075c6fd7c2356fd1c5e70ca74` block 68049790 |
| Divergence recorded | 2753 bps (price A 1.322, price B 1.002) |
| Source block echoed on both chains | 59901740 |
| Time from dump to both venues paused | 6 Base blocks = 1.2 s, 2 s by timestamp |
| Guard on Lasna | `0xD48C67761aDa53158d85C1190bEdbf20aa20E4b8` |

## Latency result (measured, not estimated)

Four runs on 17 Nov 2026, Base Sepolia (84532) -> Reactive Lasna (5318007) -> Base Sepolia:

| Run | Blocks | At 200 ms/block | Timestamp delta |
|---|---|---|---|
| 1 | 4 | 0.8 s | 0 s |
| 2 | 8 | 1.6 s | 1 s |
| 3 | 4 | 0.8 s | 1 s |
| 4 | 7 | 1.4 s | 1 s |

Average 1.3 s, fastest 0.8 s, slowest 1.6 s. The first run went from block 59897186 to 59897190,
and its callback tx is `0xa9db0416e0ae4d80b82464d86316bc2f7262c61ad75085bb920448981dedec1d`.

The address injected into the first payload slot was `0x3869253c...` , the reactive contract itself,
not the deployer EOA.

## What is in here

| File | Role |
|---|---|
| `src/PingOrigin.sol` | Origin contract on Base Sepolia. `ping(nonce)` emits `Ping(sender, nonce, sentAt, pingBlock)` |
| `src/PingReactive.sol` | Reactive contract on Lasna. Subscribes to `Ping`, calls `SYSTEM.requestCallbackV_1_0` in `react()` |
| `src/PongSink.sol` | Destination contract on Base Sepolia. Accepts the callback and records arrival time and block |
| `test/Loop.t.sol` | 5 tests: origin event shape, payload layout, sink auth (proxy only, right reactive only) |
| `tools/newkey.py` | Generates the burner key into `.env` without printing it |
| `tools/faucet.sh` | Swaps Base Sepolia ETH for Lasna lREACT through Reactive's faucet contract |
| `tools/run_loop.py` | Full deploy + measure in one run |
| `tools/measure.py` | Ping and measure against already deployed contracts |

Deployed addresses from the last run:

```
origin    0x807d39D27c5BC04427C17c5f523b8C00Ea0ad863   Base Sepolia
sink      0x81806E13aAEb4999C248FAf65BDCf1b7F3b5566b   Base Sepolia
reactive  0x3869253c23720ee4f9cCA89174cACcBDe76E9073   Lasna
```

## Three traps that cost the most time

1. **Use `reactive-lib-omni`, not `reactive-lib`.** The legacy library (v0.2.0, last commit 2025) does not
   match Omni: its `vmOnly` modifier reverts inside the RVM, its `SERVICE_ADDR` points at a legacy alias
   instead of `0x8888...`, and its `Callback` event path is deprecated. Omni wants
   `SYSTEM.requestCallbackV_1_0(config)`.
2. **Debt blocks execution, and a plain transfer does not clear it.** `debt(address) > 0` stops the system
   contract from calling `react()` at all, silently. Fund through `depositTo(address)` on the system contract
   (Reactive side) and on the callback proxy (destination side), not with a bare transfer.
3. **The destination contract must be funded too.** The proxy bills the callback recipient in the destination
   chain's native token. With zero reserves the callback never lands and the failure shows up only on Reactscan
   under Callbacks, with an error string like `invalid payload format` that points nowhere near the real cause.

## Reproduce

```bash
./tools/faucet.sh 0.004ether          # Base Sepolia ETH -> lREACT on Lasna
python3 tools/run_loop.py             # deploy, fund both sides, ping, measure
python3 tools/measure.py <origin> <sink> <reactive>   # extra samples
```

`results.json` holds the last sample.
