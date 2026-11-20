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
| DivergenceGuard | Reactive Lasna 5318007 | `0x7DaC6d62F8eEce510466014C64677E5223931BAf` |
| GuardCallback | Base Sepolia 84532 | `0x9826cE3430d8c9B7B413425755841E845b04002E` |
| GuardCallback | Unichain Sepolia 1301 | `0x93356Ae33DaE0cbCDA2E7a223c5D32564E0911f3` |
| MiniPool (ALPHA/BETA) | Base Sepolia 84532 | `0x153f483ab58C67b6e11DebC514DBCB383d45d015` |
| MiniPool (ALPHA/BETA) | Unichain Sepolia 1301 | `0x02F44658aCC569d1bF27cF50223a35696DbA4878` |

## Evidence from one real run

| Step | Transaction | Block |
|---|---|---|
| Dump of 150 ALPHA on Base Sepolia, price 1.0000 to 1.3220 | `0x88efac938c064bcad5a642fdbcb6c130d4f539d75e5674d1c113a384564b58dd` | 59914213 |
| Reactive execution on Lasna (both callback requests) | `0x7c377abe23561c03ce99e26f1af0a1023d2a3be24fcc90e297c0506b7e494625` | 8557547 |
| Base venue paused by the guard | `0xa1f824cdc92dccb12cb990f365c96fb5d248b7b50a15ea8832f613ea89d30751` | 59914220 |
| Unichain venue paused by the same event | `0xbd3e23498bc2062264c85575720f2a437b3344a9d9fe6af5022cb228e17f3113` | 68052285 |

Divergence recorded: 2753 bps (27.53%). Source block echoed on both chains:
59914213. Base block delta from the dump to the pause: 7 blocks at 200 ms, which is 1.4 seconds.
Timestamps agree to 1 seconds.

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
tools/build_subs.py        narration clips to one audio track plus the caption cues
tools/render_film.py       builds docs/demo.mp4 from the cast, the cards, the stills and the captions
tools/sync_page.py         rewrites the page config from demo.json and guard_result.json
tools/sync_docs.py         rewrites the address and evidence tables in README and SUBMISSION
tools/audit.py             links, on-chain truth, document consistency, video, repo hygiene
docs/index.html            the live page (reads the three chains directly from the browser;
                           falls back to the recorded run, labelled, if a chain is unreachable)
branding/                  logo exports: icon, avatar, lockups and svg, from tools/export_logo.py
scripts/verify.sh          one command, no wallet, exit code
```

```bash
forge build && forge test        # 21 tests
./scripts/verify.sh              # checks the live deployment, no wallet needed
python3 tools/audit.py           # links, chain truth, docs consistency, video, hygiene
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
