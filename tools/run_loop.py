#!/usr/bin/env python3
"""Deploy the Omni ping/pong loop and measure the full event -> callback latency.

Order matters: the sink needs the reactive contract's address (the proxy injects it into the payload),
while the reactive contract needs the sink to request a callback, so the sink is set after both exist.

Usage: python3 tools/run_loop.py
Writes results.json. Reads PRIVATE_KEY from .env, never prints it.
"""
import json
import pathlib
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_RPC = "https://sepolia.base.org"
LASNA_RPC = "https://lasna-rpc.rnk.dev/"
BASE_CHAIN_ID = 84532
CALLBACK_PROXY = "0x476F44b11F5C942c58f4C8E3d0300E5710743585"
SYSTEM = "0x8888888888888888888888888888888888888888"
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"

ENV = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()
PK = ENV["PRIVATE_KEY"]
DEPLOYER = ENV["DEPLOYER"]


def sh(binary, *args, json_out=False):
    cmd = [str(FOUNDRY / binary)] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if p.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd).replace(PK, '<redacted>')}\n{p.stdout}\n{p.stderr}")
    return json.loads(p.stdout) if json_out else p.stdout


def create(contract, rpc, args=(), value=None):
    cmd = ["create", contract, "--rpc-url", rpc, "--private-key", PK, "--broadcast", "--json"]
    if value:
        cmd += ["--value", value]
    if args:
        cmd += ["--constructor-args", *args]
    out = sh("forge", *cmd, json_out=True)
    return out["deployedTo"], out["transactionHash"]


def send(target, signature, args=(), rpc=BASE_RPC, value=None):
    cmd = ["send", target, signature, *args, "--rpc-url", rpc, "--private-key", PK, "--json"]
    if value:
        cmd += ["--value", value]
    return sh("cast", *cmd, json_out=True)


def rpc_call(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def block_number():
    return int(rpc_call(BASE_RPC, "eth_blockNumber", [])["result"], 16)


def logs_for(address, start, end):
    out = []
    while start <= end:
        stop = min(start + 190, end)
        res = rpc_call(BASE_RPC, "eth_getLogs", [{"address": address, "fromBlock": hex(start), "toBlock": hex(stop)}])
        out += res.get("result", [])
        start = stop + 1
    return out


def main():
    topic = sh("cast", "keccak", "Ping(address,uint256,uint256,uint256)").strip()
    print("topic", topic)

    origin, origin_tx = create("src/PingOrigin.sol:PingOrigin", BASE_RPC)
    print("origin    ", origin, origin_tx)

    reactive, rc_tx = create(
        "src/PingReactive.sol:PingReactive",
        LASNA_RPC,
        [str(BASE_CHAIN_ID), str(BASE_CHAIN_ID), origin, topic],
        value="0.02ether",
    )
    print("reactive  ", reactive, rc_tx)

    sink, sink_tx = create("src/PongSink.sol:PongSink", BASE_RPC, [CALLBACK_PROXY, reactive])
    print("sink      ", sink, sink_tx)

    print("setSink   ", send(reactive, "setSink(address)", [sink], rpc=LASNA_RPC).get("transactionHash"))
    print("rc deposit", send(SYSTEM, "depositTo(address)", [reactive], rpc=LASNA_RPC, value="0.05ether").get("transactionHash"))
    print("sink dep  ", send(CALLBACK_PROXY, "depositTo(address)", [sink], value="0.003ether").get("transactionHash"))

    nonce = int(time.time()) % 1_000_000
    t0 = time.time()
    receipt = send(origin, "ping(uint256)", [str(nonce)])
    print("ping tx   ", receipt["transactionHash"], "nonce", nonce)

    ping_log = next(l for l in receipt["logs"] if l["address"].lower() == origin.lower())
    data = ping_log["data"][2:]
    sent_at = int(data[0:64], 16)
    ping_block = int(data[64:128], 16)
    print("origin block", ping_block, "sentAt", sent_at)

    found = None
    deadline = time.time() + 240
    scanned = ping_block - 1
    while time.time() < deadline:
        head = block_number() - 2
        for e in logs_for(sink, max(scanned + 1, ping_block), head):
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
        "deployer": DEPLOYER,
    }
    (ROOT / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
