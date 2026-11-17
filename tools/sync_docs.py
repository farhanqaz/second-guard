#!/usr/bin/env python3
"""Regenerate the address and evidence sections of README.md and SUBMISSION.md from the live run.

Run after prepare_demo.py and attack.py so the prose can never quote a retired contract.

Usage: python3 tools/sync_docs.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def tables():
    demo = json.loads((ROOT / "demo.json").read_text())
    res = json.loads((ROOT / "guard_result.json").read_text())
    base, uni, guard = demo["base"], demo["uni"], demo["guard"]
    blocks = res["base"]["blocks"]
    seconds = round(blocks * 0.2, 1)

    readme_addr = f"""| Contract | Chain | Address |
|---|---|---|
| DivergenceGuard | Reactive Lasna 5318007 | `{guard['address']}` |
| GuardCallback | Base Sepolia 84532 | `{guard['baseCallback']}` |
| GuardCallback | Unichain Sepolia 1301 | `{guard['uniCallback']}` |
| MiniPool (ALPHA/BETA) | Base Sepolia 84532 | `{base['pool']}` |
| MiniPool (ALPHA/BETA) | Unichain Sepolia 1301 | `{uni['pool']}` |

"""
    sub_addr = f"""| Contract | Chain | Address |
|---|---|---|
| DivergenceGuard | Reactive Lasna 5318007 | `{guard['address']}` |
| GuardCallback | Base Sepolia 84532 | `{guard['baseCallback']}` |
| GuardCallback | Unichain Sepolia 1301 | `{guard['uniCallback']}` |
| MiniPool (ALPHA/BETA) | Base Sepolia 84532 | `{base['pool']}` |
| MiniPool (ALPHA/BETA) | Unichain Sepolia 1301 | `{uni['pool']}` |
| MiniERC20 ALPHA / BETA | Base Sepolia 84532 | `{base['tokenA']}` / `{base['tokenB']}` |
| MiniERC20 ALPHA / BETA | Unichain Sepolia 1301 | `{uni['tokenA']}` / `{uni['tokenB']}` |

"""
    evidence = f"""| Step | Transaction | Block |
|---|---|---|
| Dump of 150 ALPHA on Base Sepolia, price 1.0000 to 1.3220 | `{res['attack']['tx']}` | {res['attack']['block']} |
| Reactive execution on Lasna (both callback requests) | `{res['lasna_tx']}` | {res['lasna_block']} |
| Base venue paused by the guard | `{res['base']['tx']}` | {res['base']['block']} |
| Unichain venue paused by the same event | `{res['uni']['tx']}` | {res['uni']['block']} |

Divergence recorded: {res['divergenceBps']} bps ({res['divergenceBps'] / 100:.2f}%). Source block echoed on both chains:
{res['sourceBlock']}. Base block delta from the dump to the pause: {blocks} blocks at 200 ms, which is {seconds} seconds.
Timestamps agree to {res['base']['delta_s']} seconds.
"""
    return readme_addr, sub_addr, evidence, seconds, blocks


def swap(text, start_heading, end_heading, body):
    pattern = re.compile(
        re.escape(start_heading) + r".*?(?=" + re.escape(end_heading) + ")", flags=re.S
    )
    return pattern.sub(start_heading + "\n\n" + body, text, count=1)


def main():
    readme_addr, sub_addr, evidence, seconds, blocks = tables()

    rp = ROOT / "README.md"
    readme = rp.read_text()
    readme = swap(readme, "## Deployed on public testnets", "## Evidence from one real run", readme_addr)
    readme = swap(readme, "## Evidence from one real run", "## Measured latency, separately", evidence + "\n")
    rp.write_text(readme)

    sp = ROOT / "SUBMISSION.md"
    sub = sp.read_text()
    guard_addr = json.loads((ROOT / "demo.json").read_text())["guard"]["address"]
    sub = re.sub(r"(\| Guard on Lasna \| https://lasna\.reactscan\.net/address/)0x[0-9a-fA-F]{40}",
                 rf"\g<1>{guard_addr}", sub)
    sub = swap(sub, "## Deployed contracts", "## The full loop, in hashes", sub_addr)
    sub = swap(sub, "## The full loop, in hashes", "## Execution evidence", evidence + "\n")
    sp.write_text(sub)

    print(json.dumps({"seconds": seconds, "blocks": blocks}))


if __name__ == "__main__":
    main()
