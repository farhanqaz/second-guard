#!/usr/bin/env python3
"""Fire one ping and measure the callback round trip for already deployed contracts.

Usage: python3 tools/measure.py <origin> <sink> <reactive>
"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_RPC = "https://sepolia.base.org"
BASE_LOG_RPC = "https://base-sepolia-rpc.publicnode.com"
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"

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


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        url, body, {"content-type": "application/json", "user-agent": "reactive-spike/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    origin, sink, reactive = sys.argv[1:4]
    nonce = int(time.time()) % 1_000_000
    t0 = time.time()
    receipt = sh(
        "cast", "send", origin, "ping(uint256)", str(nonce),
        "--rpc-url", BASE_RPC, "--private-key", PK, "--json", json_out=True,
    )
    ping_log = next(l for l in receipt["logs"] if l["address"].lower() == origin.lower())
    data = ping_log["data"][2:]
    sent_at, ping_block = int(data[0:64], 16), int(data[64:128], 16)
    print("ping", receipt["transactionHash"], "block", ping_block, "nonce", nonce, flush=True)

    found = None
    deadline = time.time() + 240
    scanned = ping_block - 1
    while time.time() < deadline:
        head = int(rpc(BASE_LOG_RPC, "eth_blockNumber", [])["result"], 16) - 2
        start = max(scanned + 1, ping_block)
        while start <= head:
            stop = min(start + 190, head)
            res = rpc(BASE_LOG_RPC, "eth_getLogs", [{"address": sink, "fromBlock": hex(start), "toBlock": hex(stop)}])
            for e in res.get("result", []):
                d = e["data"][2:]
                if int(e["topics"][1], 16) != nonce:
                    continue
                found = {
                    "nonce": nonce,
                    "ping_timestamp": int(d[0:64], 16),
                    "ping_block": int(d[64:128], 16),
                    "arrived_timestamp": int(d[128:192], 16),
                    "arrived_block": int(d[192:256], 16),
                    "reactive_injected": "0x" + d[256 + 24:256 + 64],
                    "callback_tx": e["transactionHash"],
                }
                break
            start = stop + 1
            if found:
                break
        scanned = head
        if found:
            break
        time.sleep(3)

    if not found:
        raise SystemExit("no callback within 240s")

    block_delta = found["arrived_block"] - found["ping_block"]
    result = {
        **found,
        "latency_blocks": block_delta,
        "latency_blocks_200ms": round(block_delta * 0.2, 2),
        "latency_timestamp_s": found["arrived_timestamp"] - found["ping_timestamp"],
        "wall_clock_s": round(time.time() - t0, 2),
        "origin": origin,
        "sink": sink,
        "reactive": reactive,
    }
    (ROOT / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
