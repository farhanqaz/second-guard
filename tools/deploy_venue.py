#!/usr/bin/env python3
"""Deploy one demo venue (two tokens, one pool, seeded at 1:1) on a chain.

Usage: python3 tools/deploy_venue.py base|uni
Writes/merges addresses into demo.json.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"

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


def create(contract, chain, args=(), value=None):
    cmd = ["create", contract, "--rpc-url", chain["rpc"], "--private-key", PK, "--broadcast", "--json"]
    if value:
        cmd += ["--value", value]
    if args:
        cmd += ["--constructor-args", *args]
    out = sh("forge", *cmd, json_out=True)
    return out["deployedTo"]


def send(chain, target, signature, args=(), value=None):
    cmd = ["send", target, signature, *args, "--rpc-url", chain["rpc"], "--private-key", PK, "--json"]
    if value:
        cmd += ["--value", value]
    return sh("cast", *cmd, json_out=True)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "base"
    chain = CHAINS[which]
    state = json.loads((ROOT / "demo.json").read_text()) if (ROOT / "demo.json").exists() else {}

    token_a = create("src/MiniERC20.sol:MiniERC20", chain, ["Alpha", "ALPHA"])
    token_b = create("src/MiniERC20.sol:MiniERC20", chain, ["Beta", "BETA"])
    print(which, "tokenA", token_a)
    print(which, "tokenB", token_b)

    pool = create("src/MiniPool.sol:MiniPool", chain, [token_a, token_b])
    print(which, "pool  ", pool)

    one_million = str(1_000_000 * 10**18)
    thousand = str(1_000 * 10**18)
    send(chain, token_a, "mint(address,uint256)", [ENV["DEPLOYER"], one_million])
    send(chain, token_b, "mint(address,uint256)", [ENV["DEPLOYER"], one_million])
    send(chain, token_a, "approve(address,uint256)", [pool, one_million])
    send(chain, token_b, "approve(address,uint256)", [pool, one_million])
    send(chain, pool, "seed(uint256,uint256)", [thousand, thousand])

    price = sh("cast", "call", pool, "price()(uint256)", "--rpc-url", chain["rpc"]).strip()
    print(which, "price ", price)

    state[which] = {
        "chainId": chain["id"],
        "rpc": chain["rpc"],
        "proxy": chain["proxy"],
        "tokenA": token_a,
        "tokenB": token_b,
        "pool": pool,
        "price": price,
    }
    (ROOT / "demo.json").write_text(json.dumps(state, indent=2))
    print(json.dumps(state[which], indent=2))


if __name__ == "__main__":
    main()
