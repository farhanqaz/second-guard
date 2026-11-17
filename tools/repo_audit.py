#!/usr/bin/env python3
"""Check the repo for anything that should not be public: secrets, local state, junk.

Scans the working tree AND the full git history, because a file removed today is still readable in
an older commit. Prints findings only, never the secret value itself.

Usage: python3 tools/repo_audit.py
"""
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent

SUSPECT_NAMES = re.compile(
    r"(\.env|\.key$|\.pem$|id_rsa|id_ed25519|keystore|wallet|secret|credential|\.log$|\.bak$|\.swp$|"
    r"\.DS_Store|\.sqlite|\.db$|node_modules|__pycache__|\.pyc$)", re.I)
PATTERNS = {
    "private key (64 hex)": re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])"),
    "mnemonic-ish words": re.compile(r"\b(abandon|mnemonic|seed phrase)\b", re.I),
    "github token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai/anthropic key": re.compile(r"(sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9\-]{20,})"),
    "google api key": re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    "slack token": re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    "aws key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "pem block": re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9\-_.]{20,}"),
}


def git(*args, text=True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=text).stdout


def main():
    tracked = git("ls-files").split()
    print(f"tracked files: {len(tracked)}")

    print("\n== names that look local or secret")
    flagged = [t for t in tracked if SUSPECT_NAMES.search(t)]
    for t in flagged:
        print("  FLAG", t)
    if not flagged:
        print("  none")

    print("\n== secret patterns in the working tree")
    hits = 0
    for t in tracked:
        p = ROOT / t
        if not p.exists() or p.stat().st_size > 2_000_000 or p.name == "repo_audit.py":
            continue  # the detector's own patterns are not secrets
        try:
            body = p.read_text(errors="ignore")
        except Exception:
            continue
        for label, rx in PATTERNS.items():
            for m in rx.finditer(body):
                if label == "private key (64 hex)":
                    # hashes and addresses are not secrets; only flag when prefixed like a key
                    line = body[max(0, m.start() - 40):m.start()].lower()
                    if "private" not in line and "key" not in line:
                        continue
                print(f"  HIT  {label} in {t}")
                hits += 1
    if not hits:
        print("  none")

    print("\n== the actual values from .env, anywhere in history")
    env = {}
    envp = ROOT / ".env"
    if envp.exists():
        for line in envp.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for key in ("PRIVATE_KEY",):
        val = env.get(key)
        if not val:
            continue
        found = subprocess.run(
            ["git", "grep", "-I", "-l", "--all-match", val, git("rev-list", "--all").split()[-1] if False else "HEAD"],
            cwd=ROOT, capture_output=True, text=True).stdout.strip()
        # fastest reliable check: scan every blob in history
        blobs = git("rev-list", "--objects", "--all").splitlines()
        leaked = []
        for line in blobs:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            sha, name = parts
            body = subprocess.run(["git", "cat-file", "-p", sha], cwd=ROOT,
                                  capture_output=True).stdout
            if val.encode() in body:
                leaked.append(name)
        print("  PRIVATE_KEY in history:", sorted(set(leaked)) if leaked else "no")
        break

    print("\n== biggest tracked files")
    sizes = sorted(((ROOT / t).stat().st_size, t) for t in tracked if (ROOT / t).exists())
    for size, t in sizes[-6:][::-1]:
        print(f"  {size/1024:8.1f} KB  {t}")

    print("\n== gitignore covers")
    gi = (ROOT / ".gitignore").read_text() if (ROOT / ".gitignore").exists() else ""
    for want in (".env", "out/", "cache/", "broadcast/"):
        print(f"  {want:12} {'yes' if want in gi else 'NO'}")

    print("\n== json files tracked (state can leak local paths)")
    for t in tracked:
        if t.endswith(".json"):
            body = (ROOT / t).read_text(errors="ignore")
            note = "has absolute path" if str(pathlib.Path.home()) in body else "ok"
            print(f"  {t:40} {note}")


if __name__ == "__main__":
    main()
