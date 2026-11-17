#!/usr/bin/env python3
"""Prepare a clean demo state: both venues live at 1.000, guard wired, reserves funded.

Leaves the system armed and idle so the attack can be recorded separately.

Usage: python3 tools/prepare_demo.py
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"
LASNA_RPC = "https://lasna-rpc.rnk.dev/"
SYSTEM = "0x8888888888888888888888888888888888888888"

CHAINS = {
    "base": {"rpc": "https://sepolia.base.org", "id": 84532, "proxy": "0x476F44b11F5C942c58f4C8E3d0300E5710743585"},
    "uni": {"rpc": "https://sepolia.unichain.org", "id": 1301, "proxy": "0x775c9B990ADe401060B78D0e98684eEf8d2466C1"},
}

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
    cmd = ["create", contract, "--rpc-url", rpc, "--private-key", PK, "--broadcast", "--json",
           "--gas-limit", "1500000"]
    if value:
        cmd += ["--value", value]
    if args:
        cmd += ["--constructor-args", *args]
    out = sh("forge", *cmd, json_out=True)
    return out["deployedTo"]


def send(target, signature, args=(), rpc=None, value=None):
    cmd = ["send", target, signature, *args, "--rpc-url", rpc, "--private-key", PK, "--json"]
    if value:
        cmd += ["--value", value]
    return sh("cast", *cmd, json_out=True)


def deploy_venue(which):
    chain = CHAINS[which]
    token_a = create("src/MiniERC20.sol:MiniERC20", chain["rpc"], ["Alpha", "ALPHA"])
    token_b = create("src/MiniERC20.sol:MiniERC20", chain["rpc"], ["Beta", "BETA"])
    pool = create("src/MiniPool.sol:MiniPool", chain["rpc"], [token_a, token_b])

    million = str(1_000_000 * 10**18)
    thousand = str(1_000 * 10**18)
    send(token_a, "mint(address,uint256)", [ENV["DEPLOYER"], million], rpc=chain["rpc"])
    send(token_b, "mint(address,uint256)", [ENV["DEPLOYER"], million], rpc=chain["rpc"])
    send(token_a, "approve(address,uint256)", [pool, million], rpc=chain["rpc"])
    send(token_b, "approve(address,uint256)", [pool, million], rpc=chain["rpc"])
    send(pool, "seed(uint256,uint256)", [thousand, thousand], rpc=chain["rpc"])
    print(f"{which} venue: pool {pool}")
    return {"chainId": chain["id"], "rpc": chain["rpc"], "proxy": chain["proxy"], "tokenA": token_a,
            "tokenB": token_b, "pool": pool, "price": "1000000000000000000"}


def main():
    demo = {"base": deploy_venue("base"), "uni": deploy_venue("uni")}
    base, uni = demo["base"], demo["uni"]

    topic = sh("cast", "keccak", "Swap(address,bool,uint256,uint256,uint256,uint256,uint256)").strip()
    guard = create(
        "src/DivergenceGuard.sol:DivergenceGuard",
        LASNA_RPC,
        ["[%d,%d]" % (base["chainId"], uni["chainId"]), "[%s,%s]" % (base["pool"], uni["pool"]), topic, "500", "600", "60"],
        value="0.02ether",
    )
    base_cb = create("src/GuardCallback.sol:GuardCallback", base["rpc"], [base["proxy"], guard, base["pool"]])
    uni_cb = create("src/GuardCallback.sol:GuardCallback", uni["rpc"], [uni["proxy"], guard, uni["pool"]])
    print("guard", guard)
    print("callbacks", base_cb, uni_cb)

    send(guard, "setCallbacks(address,address)", [base_cb, uni_cb], rpc=LASNA_RPC)
    send(base["pool"], "setGuard(address)", [base_cb], rpc=base["rpc"])
    send(uni["pool"], "setGuard(address)", [uni_cb], rpc=uni["rpc"])
    send(SYSTEM, "depositTo(address)", [guard], rpc=LASNA_RPC, value="0.05ether")
    send(base["proxy"], "depositTo(address)", [base_cb], rpc=base["rpc"], value="0.003ether")
    send(uni["proxy"], "depositTo(address)", [uni_cb], rpc=uni["rpc"], value="0.003ether")

    # calibrate the second feed so the guard knows both prices before the attack
    send(uni["pool"], "swap(bool,uint256)", ["true", str(1 * 10**18)], rpc=uni["rpc"])
    time.sleep(8)

    demo["guard"] = {"address": guard, "baseCallback": base_cb, "uniCallback": uni_cb}
    (ROOT / "demo.json").write_text(json.dumps(demo, indent=2))
    print(json.dumps(demo["guard"], indent=2))


if __name__ == "__main__":
    main()
