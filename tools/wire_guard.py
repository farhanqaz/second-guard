#!/usr/bin/env python3
"""Wire the cross-venue guard end to end and run one attack.

Needs demo.json with both venues (base and uni) already deployed, plus lREACT on Lasna and a little ETH
on both destination chains for callback reserves.

Usage: python3 tools/wire_guard.py
"""
import json
import pathlib
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"
LASNA_RPC = "https://lasna-rpc.rnk.dev/"
SYSTEM = "0x8888888888888888888888888888888888888888"
BASE_LOG_RPC = "https://base-sepolia-rpc.publicnode.com"

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


def create(contract, rpc, args=(), value=None):
    cmd = ["create", contract, "--rpc-url", rpc, "--private-key", PK, "--broadcast", "--json"]
    if value:
        cmd += ["--value", value]
    if args:
        cmd += ["--constructor-args", *args]
    out = sh("forge", *cmd, json_out=True)
    return out["deployedTo"], out["transactionHash"]


def send(target, signature, args=(), rpc=None, value=None):
    cmd = ["send", target, signature, *args, "--rpc-url", rpc, "--private-key", PK, "--json"]
    if value:
        cmd += ["--value", value]
    return sh("cast", *cmd, json_out=True)


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json", "user-agent": "spike/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    demo = json.loads((ROOT / "demo.json").read_text())
    base, uni = demo["base"], demo["uni"]
    topic = sh("cast", "keccak", "Swap(address,bool,uint256,uint256,uint256,uint256,uint256)").strip()
    print("swap topic", topic)

    guard, guard_tx = create(
        "src/DivergenceGuard.sol:DivergenceGuard",
        LASNA_RPC,
        ["[%d,%d]" % (base["chainId"], uni["chainId"]), "[%s,%s]" % (base["pool"], uni["pool"]), topic, "500", "600", "60"],
        value="0.02ether",
    )
    print("guard", guard, guard_tx)

    base_cb, base_cb_tx = create(
        "src/GuardCallback.sol:GuardCallback", base["rpc"], [base["proxy"], guard, base["pool"]]
    )
    print("base callback", base_cb, base_cb_tx)

    uni_cb, uni_cb_tx = create("src/GuardCallback.sol:GuardCallback", uni["rpc"], [uni["proxy"], guard, uni["pool"]])
    print("uni callback", uni_cb, uni_cb_tx)

    print("setCallbacks", send(guard, "setCallbacks(address,address)", [base_cb, uni_cb], rpc=LASNA_RPC)["transactionHash"])
    print("base setGuard", send(base["pool"], "setGuard(address)", [base_cb], rpc=base["rpc"])["transactionHash"])
    print("uni setGuard", send(uni["pool"], "setGuard(address)", [uni_cb], rpc=uni["rpc"])["transactionHash"])

    print("guard reserves", send(SYSTEM, "depositTo(address)", [guard], rpc=LASNA_RPC, value="0.05ether")["transactionHash"])
    print("base cb reserves", send(base["proxy"], "depositTo(address)", [base_cb], rpc=base["rpc"], value="0.003ether")["transactionHash"])
    print("uni cb reserves", send(uni["proxy"], "depositTo(address)", [uni_cb], rpc=uni["rpc"], value="0.003ether")["transactionHash"])

    demo["guard"] = {"address": guard, "tx": guard_tx, "baseCallback": base_cb, "uniCallback": uni_cb}
    (ROOT / "demo.json").write_text(json.dumps(demo, indent=2))

    # one attack: dump the base venue, watch the guard stop both
    head = int(rpc(BASE_LOG_RPC, "eth_blockNumber", [])["result"], 16)
    dump = send(
        base["pool"], "swap(bool,uint256)", ["true", str(150 * 10**18)], rpc=base["rpc"]
    )
    print("dump tx", dump["transactionHash"], "block", int(dump["blockNumber"], 16))
    attack_block = int(dump["blockNumber"], 16)

    deadline = time.time() + 240
    paused = False
    while time.time() < deadline:
        for venue, label in ((base, "base"), (uni, "uni")):
            state = sh("cast", "call", venue["pool"], "paused()(bool)", "--rpc-url", venue["rpc"]).strip()
            if "true" in state:
                print(f"{label} pool paused")
                paused = True
        if paused:
            break
        time.sleep(3)

    if not paused:
        raise SystemExit("no pause within 240s")

    head_after = int(rpc(BASE_LOG_RPC, "eth_blockNumber", [])["result"], 16)
    result = {
        "attackTx": dump["transactionHash"],
        "attackBlock": attack_block,
        "headAfter": head_after,
        "blocksElapsed": head_after - attack_block,
        "secondsAt200ms": round((head_after - attack_block) * 0.2, 1),
        "basePaused": sh("cast", "call", base["pool"], "paused()(bool)", "--rpc-url", base["rpc"]).strip(),
        "uniPaused": sh("cast", "call", uni["pool"], "paused()(bool)", "--rpc-url", uni["rpc"]).strip(),
        "guard": guard,
    }
    (ROOT / "guard_result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
