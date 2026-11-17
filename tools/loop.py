#!/usr/bin/env python3
"""Deploy the ping/pong loop, fire one ping, and measure the full event -> callback latency.

Usage: python3 tools/loop.py [--skip-deploy <origin> <sink> <rc>]

Reads PRIVATE_KEY from .env. Never prints the key.
"""
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_RPC = "https://sepolia.base.org"
LASNA_RPC = "https://lasna-rpc.rnk.dev/"
BASE_CHAIN_ID = 84532
CALLBACK_PROXY_BASE_SEPOLIA = "0x476F44b11F5C942c58f4C8E3d0300E5710743585"
PING_TOPIC = None  # filled in from cast keccak


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
PK = ENV["PRIVATE_KEY"]
DEPLOYER = ENV["DEPLOYER"]
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def sh(*args, json_out=False):
    cmd = [str(FOUNDRY / "forge")] + list(args) if args[0] == "forge" else [str(FOUNDRY / args[0])] + list(args[1:])
    p = run(cmd)
    if p.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return json.loads(p.stdout) if json_out else p.stdout


def create(contract, rpc, args=(), value=None):
    cmd = ["forge", "create", contract, "--rpc-url", rpc, "--private-key", PK, "--json"]
    if args:
        cmd += ["--constructor-args", *args]
    if value:
        cmd += ["--value", value]
    out = sh(*cmd, json_out=True)
    return out["deployedTo"], out["transactionHash"]


def send(sig_args, rpc, value=None):
    cmd = ["cast", "send", *sig_args, "--rpc-url", rpc, "--private-key", PK, "--json"]
    if value:
        cmd += ["--value", value]
    return sh(*cmd, json_out=True)


def main():
    ping_topic = sh("cast", "keccak", "Ping(address,uint256,uint256,uint256)").strip()
    print("ping topic:", ping_topic)

    if "--skip-deploy" in sys.argv:
        i = sys.argv.index("--skip-deploy")
        origin, sink, rc = sys.argv[i + 1:i + 4]
    else:
        origin, origin_tx = create("src/PingOrigin.sol:PingOrigin", BASE_RPC)
        print("PingOrigin      ", origin, "tx", origin_tx)
        sink, sink_tx = create("src/PongSink.sol:PongSink", BASE_RPC, [CALLBACK_PROXY_BASE_SEPOLIA])
        print("PongSink        ", sink, "tx", sink_tx)
        rc, rc_tx = create(
            "src/PingReactive.sol:PingReactive",
            LASNA_RPC,
            [str(BASE_CHAIN_ID), str(BASE_CHAIN_ID), origin, ping_topic, sink],
        )
        print("PingReactive    ", rc, "tx", rc_tx)
        # fund the reactive contract so it can pay for event delivery and callback gas
        fund = send([rc, "--value", "0.05ether"], LASNA_RPC)
        print("fund rc         ", fund.get("transactionHash"))

    nonce = int(time.time()) % 1_000_000
    t0 = time.time()
    receipt = send([origin, "ping(uint256)", str(nonce)], BASE_RPC)
    print("ping tx         ", receipt["transactionHash"], "nonce", nonce)

    # decode the Ping log out of the ping receipt
    ping_log = next(l for l in receipt["logs"] if l["address"].lower() == origin.lower())
    topics = ping_log["topics"]
    data = ping_log["data"][2:]
    sent_at = int(data[0:64], 16)
    ping_block = int(data[64:128], 16)
    print("origin block    ", ping_block, "sentAt", sent_at, "tx nonce index", int(topics[2], 16))
    print("waiting for callback ...")

    deadline = time.time() + 180
    found = None
    while time.time() < deadline:
        logs = sh(
            "cast", "logs", "--address", sink, "--from-block", str(ping_block), "--to-block", "latest",
            "--rpc-url", BASE_RPC, "--json",
        )
        entries = json.loads(logs) if isinstance(logs, str) else logs
        for e in entries:
            d = e["data"][2:]
            got_nonce = int(e["topics"][1], 16)
            if got_nonce != nonce:
                continue
            found = {
                "nonce": got_nonce,
                "ping_timestamp": int(d[0:64], 16),
                "ping_block": int(d[64:128], 16),
                "arrived_timestamp": int(d[128:192], 16),
                "arrived_block": int(d[192:256], 16),
                "callback_block_hash": e["blockHash"],
                "tx": e["transactionHash"],
            }
            break
        if found:
            break
        time.sleep(2)

    if not found:
        raise SystemExit("no callback within 180s (check RC subscription, balance, reactscan)")

    block_delta = found["arrived_block"] - found["ping_block"]
    result = {
        **found,
        "block_delta_base": block_delta,
        "latency_blocks_200ms": round(block_delta * 0.2, 2),
        "latency_timestamp_s": found["arrived_timestamp"] - found["ping_timestamp"],
        "wall_clock_s": round(time.time() - t0, 2),
        "deployer": DEPLOYER,
        "origin": origin,
        "sink": sink,
        "reactive": rc,
    }
    (ROOT / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
