#!/usr/bin/env python3
"""Generate a burner deploy key straight into a gitignored .env. Never prints the key."""
import json
import os
import pathlib
import subprocess

env = pathlib.Path(".env")
if env.exists() and "PRIVATE_KEY=" in env.read_text():
    for line in env.read_text().splitlines():
        if line.startswith("DEPLOYER="):
            print("address (existing):", line.split("=", 1)[1])
    raise SystemExit(0)

out = subprocess.run(
    ["cast", "wallet", "new", "--json"], capture_output=True, text=True, check=True
).stdout
d = json.loads(out)["data"][0]
env.write_text(f'PRIVATE_KEY={d["private_key"]}\nDEPLOYER={d["address"]}\n')
os.chmod(env, 0o600)
print("address:", d["address"])
