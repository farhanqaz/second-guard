#!/usr/bin/env python3
"""Fire the dump and report exactly how long both venues took to stop.

Timing comes from block timestamps, not from a polling loop, so the number is the chain's own view.

Usage: python3 tools/attack.py
"""
import json
import pathlib
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"
BASE_RPC = "https://sepolia.base.org"
UNI_RPC = "https://sepolia.unichain.org"

ENV = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()
PK = ENV["PRIVATE_KEY"]


def sh(binary, *args, json_out=False):
    cmd = [str(FOUNDRY / binary)] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if p.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd).replace(PK, '<redacted>')}\n{p.stdout}\n{p.stderr}")
    return json.loads(p.stdout) if json_out else p.stdout


def send(target, signature, args=(), rpc=None):
    return sh("cast", "send", target, signature, *args, "--rpc-url", rpc, "--private-key", PK, "--json", json_out=True)


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json", "user-agent": "spike/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def block_ts(url, number):
    b = rpc(url, "eth_getBlockByNumber", [hex(number), False])["result"]
    return int(b["timestamp"], 16)


def guard_log(callback, rpc_url, start, end):
    out = []
    while start <= end:
        stop = min(start + 190, end)
        out += rpc(rpc_url, "eth_getLogs", [{"address": callback, "fromBlock": hex(start), "toBlock": hex(stop)}]).get("result", [])
        start = stop + 1
    return out


def main():
    demo = json.loads((ROOT / "demo.json").read_text())
    base, uni = demo["base"], demo["uni"]
    guard = demo["guard"]

    before = int(sh("cast", "call", base["pool"], "price()(uint256)", "--rpc-url", BASE_RPC).split()[0])
    print("price before " + f"{before/1e18:.4f}", flush=True)
    dump = send(base["pool"], "swap(bool,uint256)", ["true", str(150 * 10**18)], rpc=BASE_RPC)
    attack_block = int(dump["blockNumber"], 16)
    attack_ts = block_ts(BASE_RPC, attack_block)
    print("attack", dump["transactionHash"], "block", attack_block, "ts", attack_ts, flush=True)
    print("watching for callbacks on both chains", flush=True)

    deadline = time.time() + 180
    base_log = uni_log = None
    while time.time() < deadline:
        head_b = int(rpc(BASE_RPC, "eth_blockNumber", [])["result"], 16)
        head_u = int(rpc(UNI_RPC, "eth_blockNumber", [])["result"], 16)
        if base_log is None:
            logs = guard_log(guard["baseCallback"], BASE_RPC, max(attack_block - 5, 0), head_b - 1)
            if logs:
                base_log = logs[-1]
                print("base callback landed at block " + str(int(logs[-1]["blockNumber"], 16)), flush=True)
        if uni_log is None:
            logs = guard_log(guard["uniCallback"], UNI_RPC, max(head_u - 400, 0), head_u - 1)
            if logs:
                uni_log = logs[-1]
                print("uni callback landed at block " + str(int(logs[-1]["blockNumber"], 16)), flush=True)
        if base_log and uni_log:
            break
        time.sleep(2)

    if not base_log or not uni_log:
        raise SystemExit("no pause callback seen within 180s")

    base_block = int(base_log["blockNumber"], 16)
    uni_block = int(uni_log["blockNumber"], 16)
    base_ts = block_ts(BASE_RPC, base_block)
    uni_ts = block_ts(UNI_RPC, uni_block)
    d = base_log["data"][2:]

    # the lasna side: the react execution that requested both callbacks
    lasna_block, lasna_tx = None, None
    try:
        api = "https://lasna-api.reactscan.net/callbacks?page=1&sender=" + guard["address"]
        payload = json.loads(urllib.request.urlopen(
            urllib.request.Request(api, headers={"user-agent": "spike/1.0"}), timeout=20).read())
        first = (payload.get("callbacks") or [None])[0]
        if first:
            lasna_block, lasna_tx = int(first["request_block_number"]), first["request_tx_hash"]
    except Exception as exc:
        print("notice: reactscan api unavailable (" + str(exc)[:60] + ")")

    result = {
        "attack": {"tx": dump["transactionHash"], "block": attack_block, "timestamp": attack_ts},
        "lasna_block": lasna_block,
        "lasna_tx": lasna_tx,
        "base": {"tx": base_log["transactionHash"], "block": base_block, "timestamp": base_ts,
                 "delta_s": base_ts - attack_ts, "blocks": base_block - attack_block,
                 "paused": "true" in sh("cast", "call", base["pool"], "paused()(bool)", "--rpc-url", BASE_RPC)},
        "uni": {"tx": uni_log["transactionHash"], "block": uni_block, "timestamp": uni_ts,
                "delta_s": uni_ts - attack_ts,
                "paused": "true" in sh("cast", "call", uni["pool"], "paused()(bool)", "--rpc-url", UNI_RPC)},
        "divergenceBps": int(d[128:192], 16),
        "priceA": int(d[0:64], 16),
        "priceB": int(d[64:128], 16),
        "sourceBlock": int(d[192:256], 16),
        "guard": guard["address"],
    }
    (ROOT / "guard_result.json").write_text(json.dumps(result, indent=2))
    print("")
    print("ATTACK      " + result["attack"]["tx"] + "  block " + str(attack_block))
    print("DIVERGENCE  " + str(result["divergenceBps"]) + " bps   " +
          fmt(result["priceA"]) + " vs " + fmt(result["priceB"]))
    for label in ("base", "uni"):
        r = result[label]
        print(label.upper().ljust(11) + "stopped in " + str(r["delta_s"]) + "s   block " + str(r["block"]) +
              "   paused " + str(r["paused"]).lower())
        print("            " + r["tx"])
    print("")
    print("guard " + guard["address"] + " (Lasna)")


def fmt(v):
    return f"{v/1e18:.4f}"


if __name__ == "__main__":
    main()
