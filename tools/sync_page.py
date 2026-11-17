#!/usr/bin/env python3
"""Rewrite the page config (addresses plus the recorded trip) from demo.json and guard_result.json.

Run after every fresh deployment so the page can never point at a retired contract.

Usage: python3 tools/sync_page.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "index.html"


def main():
    demo = json.loads((ROOT / "demo.json").read_text())
    res = json.loads((ROOT / "guard_result.json").read_text())
    base, uni, guard = demo["base"], demo["uni"], demo["guard"]

    cfg = (
        "const CFG = {\n"
        f'  base:{{ rpc:"{base["rpc"]}", pool:"{base["pool"]}", cb:"{guard["baseCallback"]}",\n'
        f'         chainId:{base["chainId"]}, explorer:"https://sepolia.basescan.org" }},\n'
        f'  uni:{{ rpc:"{uni["rpc"]}", pool:"{uni["pool"]}", cb:"{guard["uniCallback"]}",\n'
        f'        chainId:{uni["chainId"]}, explorer:"https://sepolia.uniscan.xyz" }},\n'
        f'  lasna:{{ rpc:"https://lasna-rpc.rnk.dev/", guard:"{guard["address"]}",\n'
        '          explorer:"https://lasna.reactscan.net" }\n'
        "};"
    )
    known = (
        "const KNOWN = [\n"
        f'  {{chain:"uni", tx:"{res["uni"]["tx"]}", block:{res["uni"]["block"]}, bps:{res["divergenceBps"]}, ts:{res["uni"]["timestamp"]}}},\n'
        f'  {{chain:"base", tx:"{res["base"]["tx"]}", block:{res["base"]["block"]}, bps:{res["divergenceBps"]}, ts:{res["base"]["timestamp"]}}}\n'
        "];"
    )

    html = PAGE.read_text()
    html = re.sub(r"const CFG = \{.*?\n\};", cfg, html, count=1, flags=re.S)
    html = re.sub(r"const KNOWN = \[.*?\n\];", known, html, count=1, flags=re.S)

    # the loop band quotes the recorded blocks and the measured gap
    html = re.sub(
        r'(<div class="k">Leg 01 · origin</div>\s*<div class="v">)\d+(</div>)',
        rf'\g<1>{res["attack"]["block"]}\g<2>', html, count=1)
    html = re.sub(
        r'(<div class="k">Leg 03 · both venues</div>\s*<div class="v">)[\d ·]+(</div>)',
        rf'\g<1>{res["base"]["block"]} · {res["uni"]["block"]}\g<2>', html, count=1)
    html = re.sub(
        r'<p>Both pools pause\. Six Base blocks separate the dump from the pause, which is [\d.]+ seconds\.</p>',
        f'<p>Both pools pause. {res["base"]["blocks"]} Base blocks separate the dump from the pause, '
        f'which is {round(res["base"]["blocks"] * 0.2, 1)} seconds.</p>', html, count=1)
    html = re.sub(
        r'(<div class="loopnote">source block )\d+( appears in both callbacks)',
        rf'\g<1>{res["sourceBlock"]}\g<2>', html, count=1)

    PAGE.write_text(html)
    print(json.dumps({"base": base["pool"], "uni": uni["pool"], "guard": guard["address"],
                      "attack": res["attack"]["block"], "blocks": res["base"]["blocks"]}, indent=1))


if __name__ == "__main__":
    main()
