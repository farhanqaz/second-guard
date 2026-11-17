# Second Guard

Cross-venue parity breaker for the Reactive Omni Buildathon, track **Every Second Counts**.

Two venues trade the same pair on two different chains. Second Guard watches both, holds both prices in
the state of one reactive contract on Reactive Lasna, and when they disagree past a threshold it stops
both venues in the same second. No keeper, no relayer, no off-chain watcher.

- Live page: https://farhanqaz.github.io/second-guard/
- Demo video (59s, real run, real hashes): https://farhanqaz.github.io/second-guard/demo.mp4
- One command verification: `./scripts/verify.sh`

## Why this needs Reactive Omni

A single-chain watchdog cannot see the divergence at all, because the divergence only exists between two
chains. Any implementation that compares two chains needs someone holding both feeds and acting on them
inside the same deterministic step. That is what a reactive contract is. On the previous 7 second blocks
the comparison would arrive after the profitable window; on Omni the measured loop is 1.2 seconds.

## How it works

```
Base Sepolia 84532                 Reactive Lasna 5318007                Unichain Sepolia 1301
------------------                 -----------------------                ---------------------
MiniPool.swap() --Swap log----->   DivergenceGuard.react()
  priceA = 1.3220                    price[84532] = 1.3220
                                     price[1301]  = 1.0020
                                     bps = 2753 > 500 ?
                                       |
                                       +--- requestCallbackV_1_0 ---> GuardCallback.pauseFromGuard()
                                       |                              MiniPool.pause()
                                       +--- requestCallbackV_1_0 ---> GuardCallback.pauseFromGuard()
                                                                      MiniPool.pause()
```

The rule keeps three guards against false positives: both feeds must be fresh (600 s staleness window), the
gap must clear the threshold (500 bps), and one trip per cooldown (60 s). The rule is a plain Solidity
contract, readable in `src/DivergenceGuard.sol`, and the payload carries the source block so both chains
record where the decision came from.

## Deployed on public testnets

| Contract | Chain | Address |
|---|---|---|
| DivergenceGuard | Reactive Lasna 5318007 | `0x85408366c1AE50491755a75378e98F2B27469818` |
| GuardCallback | Base Sepolia 84532 | `0x020Ff8Fe9623F0450Bda921B66B9dCF7cbBd4565` |
| GuardCallback | Unichain Sepolia 1301 | `0xEFD031d9EA36c800b21fd0072B1CAaCA21721fEe` |
| MiniPool (ALPHA/BETA) | Base Sepolia 84532 | `0x3c68028E292f2f8876b13C3F4b4d61b1CB03be75` |
| MiniPool (ALPHA/BETA) | Unichain Sepolia 1301 | `0x07b3674a0c0097FD0b72fF0Eb7Ec7Dc1636DDe4e` |

## Evidence from one real run

| Step | Transaction | Block |
|---|---|---|
| Dump of 150 ALPHA on Base Sepolia, price 1.0000 to 1.3220 | `0x4a5db08d2810c4e7085c6c3948e63ee646e0288bdaaadb76282d1756e6ac083d` | 59906925 |
| Base venue paused by the guard | `0x0bf250fe0f739e5867a08214801c578d9cf6460e37e144bacce677f2c5d30c48` | 59906931 |
| Unichain venue paused by the same event | `0x25600b883c7bc8e7add5d96e030d7ccf62dfa2b581cd0595eb6726bcb0fb3c3a` | 68050827 |

Divergence recorded: 2753 bps (27.53%). Source block echoed on both chains: 59906925. Base block delta from
the dump to the pause: 6 blocks at 200 ms, which is 1.2 seconds. Timestamps agree to 2 seconds.

## Measured latency, separately

Before building the product I measured the bare loop four times with a ping/pong pair of contracts
(`src/PingOrigin.sol`, `src/PingReactive.sol`, `src/PongSink.sol`, `tools/measure.py`):

| Run | Blocks | At 200 ms/block |
|---|---|---|
| 1 | 4 | 0.8 s |
| 2 | 8 | 1.6 s |
| 3 | 4 | 0.8 s |
| 4 | 7 | 1.4 s |

Average 1.3 s. Use that number, not 200 ms, when quoting the loop.

## Three traps worth knowing

1. **Use `reactive-lib-omni`, not `reactive-lib`.** The legacy library (v0.2.0, last commit 2025) breaks on
   Omni: its `vmOnly` modifier reverts inside the RVM, its `SERVICE_ADDR` points at a legacy alias instead of
   `0x8888...`, and the `Callback` event path is deprecated and rejected by the relay with
   `invalid payload format`. Omni wants `SYSTEM.requestCallbackV_1_0(config)`.
2. **Debt blocks execution, and a plain transfer does not clear it.** While `debt(address) > 0` the system
   contract will not call `react()` at all, silently. Fund through `depositTo(address)` on the system
   contract, not with a bare transfer.
3. **The destination contract must be funded too.** The callback proxy bills the recipient in the
   destination chain's native token. With zero reserves the callback never lands, and the only visible
   symptom is a `posted_error` row on Reactscan.

## Repository

```
src/MiniERC20.sol          token used by the demo venues
src/MiniPool.sol           constant-product venue, emits the price-bearing Swap event, pausable by the guard
src/DivergenceGuard.sol    the rule: two subscriptions, divergence in bps, two callback requests
src/GuardCallback.sol      destination side, authenticates the proxy and the reactive contract
src/Ping*.sol, PongSink    the latency harness used before the product was built
tools/prepare_demo.py      fresh venues, guard, callbacks, reserves, calibration
tools/attack.py            one dump, then block-timestamp timing of both pauses
tools/build_film.py        builds docs/demo.mp4 from the cast, the cards and the page stills
docs/index.html            the live page (reads the three chains directly from the browser)
scripts/verify.sh          one command, no wallet, exit code
```

```bash
forge build && forge test        # 21 tests
./scripts/verify.sh              # checks the live deployment, no wallet needed
```

`tools/prepare_demo.py` and `tools/attack.py` send transactions and need a funded key in `.env`
(`PRIVATE_KEY`, `DEPLOYER`). Everything else only reads.

## Known limits

- Testnet only. Base Sepolia, Unichain Sepolia, Reactive Lasna. No real funds.
- The venues are ours (`MiniPool`), not Uniswap. The point is the rule and the loop, not a fork of a DEX.
  Pointing the same guard at a real Uniswap pool changes the event decoder and the pause target, nothing else.
- One pair, two venues. More venues means more subscriptions, and the rule generalises to a max-min spread.
- The guard can be disarmed by its deployer. That is a demo convenience, and it is visible on chain.
- A pause stops the venue for everyone. That is the trade: liveness during an incident versus damage.
- It stops the divergence, it does not undo it. Positions already filled at the bad price stay filled.

## License

MIT.
