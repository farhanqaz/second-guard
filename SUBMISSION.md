# Submission, Reactive Omni Buildathon

**Project** Second Guard
**Track** Every Second Counts (time sensitive DeFi on Base Sepolia and Unichain Sepolia)
**Builder** solo, assisted by an AI agent

## Links

| Item | Link |
|---|---|
| Code | https://github.com/farhanqaz/second-guard |
| Live page | https://farhanqaz.github.io/second-guard/ |
| Demo video (59 s) | https://farhanqaz.github.io/second-guard/demo.mp4 |
| Guard on Lasna | https://lasna.reactscan.net/address/0x7DaC6d62F8eEce510466014C64677E5223931BAf |

## What it is

Two venues trade the same pair on two chains. A reactive contract on Reactive Lasna subscribes to the Swap
events of both, keeps both prices in its own state, and when the two venues diverge past 500 bps with both
feeds fresh it requests two callbacks in one execution and stops both venues. The divergence only exists
across chains, so a single-chain watchdog cannot express this rule at all.

## Deployed contracts

| Contract | Chain | Address |
|---|---|---|
| DivergenceGuard | Reactive Lasna 5318007 | `0x7DaC6d62F8eEce510466014C64677E5223931BAf` |
| GuardCallback | Base Sepolia 84532 | `0x9826cE3430d8c9B7B413425755841E845b04002E` |
| GuardCallback | Unichain Sepolia 1301 | `0x93356Ae33DaE0cbCDA2E7a223c5D32564E0911f3` |
| MiniPool (ALPHA/BETA) | Base Sepolia 84532 | `0x153f483ab58C67b6e11DebC514DBCB383d45d015` |
| MiniPool (ALPHA/BETA) | Unichain Sepolia 1301 | `0x02F44658aCC569d1bF27cF50223a35696DbA4878` |
| MiniERC20 ALPHA / BETA | Base Sepolia 84532 | `0x6aB3b8dC2A9558DcdCd4DEdd514ce1b69Cc9E293` / `0x080079A3EC646E97dA7De8e4dCEA0Df98BEDD940` |
| MiniERC20 ALPHA / BETA | Unichain Sepolia 1301 | `0xf1826C1BB2b95FABd1e22e5452463608fFA7771F` / `0xA44E07bE459A008624E67dB7b3bD4210d0A6Ff40` |

## The full loop, in hashes

| Step | Transaction | Block |
|---|---|---|
| Dump of 150 ALPHA on Base Sepolia, price 1.0000 to 1.3220 | `0x88efac938c064bcad5a642fdbcb6c130d4f539d75e5674d1c113a384564b58dd` | 59914213 |
| Reactive execution on Lasna (both callback requests) | `0x7c377abe23561c03ce99e26f1af0a1023d2a3be24fcc90e297c0506b7e494625` | 8557547 |
| Base venue paused by the guard | `0xa1f824cdc92dccb12cb990f365c96fb5d248b7b50a15ea8832f613ea89d30751` | 59914220 |
| Unichain venue paused by the same event | `0xbd3e23498bc2062264c85575720f2a437b3344a9d9fe6af5022cb228e17f3113` | 68052285 |

Divergence recorded: 2753 bps (27.53%). Source block echoed on both chains:
59914213. Base block delta from the dump to the pause: 7 blocks at 200 ms, which is 1.4 seconds.
Timestamps agree to 1 seconds.

## Execution evidence

- `forge test`: 21 tests, all passing, including the wiring test that etches a mock system contract and asserts
  the guard emits exactly two `requestCallbackV_1_0` calls with the right chain id, recipient, gas limit and
  payload.
- `./scripts/verify.sh`: one command, no wallet, re-runs the tests and reads the live deployment, printing PASS
  or FAIL per claim.
- The demo video is a recording of the real run (`demo/attack.cast`, rendered into `docs/demo.mp4`), not a
  re-enactment.

## What is scripted and what is not

- The two venues are demo pools we deployed. They are real contracts with real liquidity, but the assets are
  ours, not Uniswap pools. The attack in the video is a real swap against them.
- `tools/prepare_demo.py` redeploys the venues and rewires the guard, so the demo can be repeated. Each run
  produces a fresh set of addresses and hashes.
- Nothing on the reactive side is mocked: subscriptions, the reactive execution, the callback requests and the
  callbacks are all live on Lasna and on the two destination chains.

## Limits we state ourselves

- Testnet only, no real funds.
- One pair, two venues. More venues means more subscriptions.
- The deployer can disarm the guard. Visible on chain, a demo convenience.
- Pausing stops the venue for everyone. That is the trade, liveness in an incident versus damage.
- The guard stops the divergence, it does not undo fills that already happened.
