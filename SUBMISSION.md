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
| Guard on Lasna | https://lasna.reactscan.net/address/0x85408366c1AE50491755a75378e98F2B27469818 |

## What it is

Two venues trade the same pair on two chains. A reactive contract on Reactive Lasna subscribes to the Swap
events of both, keeps both prices in its own state, and when the two venues diverge past 500 bps with both
feeds fresh it requests two callbacks in one execution and stops both venues. The divergence only exists
across chains, so a single-chain watchdog cannot express this rule at all.

## Deployed contracts

| Contract | Chain | Address |
|---|---|---|
| DivergenceGuard | Reactive Lasna 5318007 | `0x85408366c1AE50491755a75378e98F2B27469818` |
| GuardCallback | Base Sepolia 84532 | `0x020Ff8Fe9623F0450Bda921B66B9dCF7cbBd4565` |
| GuardCallback | Unichain Sepolia 1301 | `0xEFD031d9EA36c800b21fd0072B1CAaCA21721fEe` |
| MiniPool (ALPHA/BETA) | Base Sepolia 84532 | `0x3c68028E292f2f8876b13C3F4b4d61b1CB03be75` |
| MiniPool (ALPHA/BETA) | Unichain Sepolia 1301 | `0x07b3674a0c0097FD0b72fF0Eb7Ec7Dc1636DDe4e` |
| MiniERC20 ALPHA / BETA | Base Sepolia 84532 | `0x1bc76f7A9eb356F0A49cC2592D3f5E03320dACB3` / `0x29Df5831c35343e1edd0aE7fe271aF21fe398bf0` |
| MiniERC20 ALPHA / BETA | Unichain Sepolia 1301 | `0x2B892980F31D088Cd038aFBCE38a4a32102202Fc` / `0xAd10D1f0Da6b8C6C685a660293CA80Db71119f9a` |

## The full loop, in hashes

| Step | Transaction | Block |
|---|---|---|
| Origin event: dump 150 ALPHA, price 1.0000 to 1.3220 | `0x4a5db08d2810c4e7085c6c3948e63ee646e0288bdaaadb76282d1756e6ac083d` | 59906925 |
| Reactive execution on Lasna (both callback requests) | `0xd3d0b16819539846aad41671a3d7ceb50df944b339e39145967da97e1c9f6609` | 8556174 |
| Callback: Base venue paused | `0x0bf250fe0f739e5867a08214801c578d9cf6460e37e144bacce677f2c5d30c48` | 59906931 |
| Callback: Unichain venue paused | `0x25600b883c7bc8e7add5d96e030d7ccf62dfa2b581cd0595eb6726bcb0fb3c3a` | 68050827 |

Recorded divergence 2753 bps. Source block 59906925 echoed on both chains. Dump to pause: 6 Base blocks at
200 ms, which is **1.2 seconds**.

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
