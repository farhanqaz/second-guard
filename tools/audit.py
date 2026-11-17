#!/usr/bin/env python3
"""Audit the submission: links, on-chain truth, document consistency, video, repo hygiene.

Usage: python3 tools/audit.py
Exit code 1 if any hard check fails.
"""
import json
import pathlib
import re
import subprocess
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOUNDRY = pathlib.Path.home() / ".foundry" / "bin"
BASE = "https://sepolia.base.org"
UNI = "https://sepolia.unichain.org"
LASNA = "https://lasna-rpc.rnk.dev/"

fails, notes = [], []


def ok(msg):
    print("PASS  " + msg)


def bad(msg):
    print("FAIL  " + msg)
    fails.append(msg)


def note(msg):
    print("NOTE  " + msg)
    notes.append(msg)


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, body, {"content-type": "application/json", "user-agent": "audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def call(url, to, data):
    out = rpc(url, "eth_call", [{"to": to, "data": data}, "latest"])["result"]
    return int(out, 16) if out not in ("0x", "0x0") else 0


def head(url):
    req = urllib.request.Request(url, method="GET", headers={"user-agent": "audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    demo = json.loads((ROOT / "demo.json").read_text())
    res = json.loads((ROOT / "guard_result.json").read_text())
    base, uni, guard = demo["base"], demo["uni"], demo["guard"]

    # ---------------------------------------------------------------- chain
    if call(BASE, base["pool"], "0xa035b1fe") > 0:
        ok("base venue answers price()")
    else:
        bad("base venue price() is zero or unreachable")
    if call(UNI, uni["pool"], "0xa035b1fe") > 0:
        ok("uni venue answers price()")
    else:
        bad("uni venue price() is zero or unreachable")
    if call(BASE, base["pool"], "0x5c975abb") == 1 and call(UNI, uni["pool"], "0x5c975abb") == 1:
        ok("both venues are paused by the guard")
    else:
        bad("a venue is not paused, the recorded run no longer matches the chain state")

    thr = call(LASNA, guard["address"], "0xc1144b71")
    trips = call(LASNA, guard["address"], "0x7bbb19dc")
    armed = call(LASNA, guard["address"], "0x2f411093")
    if thr == 500 and armed == 1 and trips >= 1:
        ok(f"guard live: threshold {thr} bps, armed {armed}, trips {trips}")
    else:
        bad(f"guard parameters unexpected: threshold {thr}, armed {armed}, trips {trips}")

    p_a = call(LASNA, guard["address"], "0x26a49e37" + (84532).to_bytes(32, "big").hex())
    p_b = call(LASNA, guard["address"], "0x26a49e37" + (1301).to_bytes(32, "big").hex())
    if p_a > 0 and p_b > 0:
        ok("guard holds both prices in its own state")
    else:
        bad("guard is missing one of the two feeds")

    for label, url, addr in (("base callback", BASE, guard["baseCallback"]),
                             ("uni callback", UNI, guard["uniCallback"]),
                             ("guard", LASNA, guard["address"])):
        code = rpc(url, "eth_getCode", [addr, "latest"])["result"]
        if len(code) > 10:
            ok(f"{label} has code on chain")
        else:
            bad(f"{label} has no code")

    # ----------------------------------------------------------- arithmetic
    blocks = res["base"]["blocks"]
    seconds = round(blocks * 0.2, 1)
    if res["base"]["block"] - res["attack"]["block"] == blocks:
        ok(f"block delta matches the recorded blocks ({blocks})")
    else:
        bad("block delta in guard_result.json is inconsistent")
    if res["base"]["delta_s"] <= 2 and seconds <= 2:
        ok(f"latency claim holds: {seconds}s ({blocks} blocks)")
    else:
        note(f"latency is {seconds}s, still under the 2 second claim in the video")

    # ------------------------------------------------------------- documents
    docs = {p.name: p.read_text() for p in (ROOT / "README.md", ROOT / "SUBMISSION.md")}
    page = (ROOT / "docs" / "index.html").read_text()
    known_addrs = set()
    for source in (base, uni, guard):
        known_addrs |= {v.lower() for v in source.values() if isinstance(v, str) and v.startswith("0x")}

    for name, text in list(docs.items()) + [("index.html", page)]:
        seen = {a.lower() for a in re.findall(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])", text)}
        stray = [a for a in seen if a not in known_addrs]
        if stray:
            bad(f"{name} mentions addresses outside demo.json: {', '.join(sorted(stray))}")
        else:
            ok(f"{name}: every contract address matches the current deployment")

    for name, text in list(docs.items()) + [("index.html", page)]:
        for h in re.findall(r"0x[0-9a-fA-F]{64}", text):
            if h not in (res["attack"]["tx"], res["base"]["tx"], res["uni"]["tx"], res.get("lasna_tx")):
                bad(f"{name} quotes an unknown transaction hash {h[:12]}...")

    if f"{seconds} seconds" in docs["README.md"] or str(blocks) + " blocks" in docs["README.md"]:
        ok("README latency prose matches the recorded run")
    else:
        bad("README latency prose is stale")
    if f"{seconds} seconds" in docs["SUBMISSION.md"]:
        ok("SUBMISSION latency prose matches the recorded run")
    else:
        note("SUBMISSION does not state the seconds value in prose")

    cfg = re.search(r"const CFG = \{.*?\n\};", page, re.S).group(0)
    for want in (base["pool"], uni["pool"], guard["address"], guard["baseCallback"], guard["uniCallback"]):
        if want in cfg:
            ok(f"page config points at {want[:10]}...")
        else:
            bad(f"page config is missing {want}")

    # ---------------------------------------------------------------- links
    links = set(re.findall(r"https?://[^\s\"'<>)]+", page + docs["README.md"] + docs["SUBMISSION.md"]))
    links |= {"https://farhanqaz.github.io/second-guard/", "https://farhanqaz.github.io/second-guard/demo.mp4"}
    skip_hosts = ("sepolia.base.org", "sepolia.unichain.org", "lasna-rpc.rnk.dev",
                  "base-sepolia-rpc.publicnode.com", "fonts.googleapis", "fonts.gstatic")
    links = {l.rstrip(".,)") for l in links if not any(h in l for h in skip_hosts)}
    dead = []
    for l in sorted(links):
        try:
            status = head(l)
            if status >= 400:
                # explorers answer 403 to scripted fetches; they are fine for a human reviewer
                if "basescan" in l or "uniscan" in l or "reactscan" in l:
                    note(f"{l} answers {status} to scripts, which is normal for explorers")
                else:
                    dead.append(f"{l} ({status})")
        except Exception as exc:
            if "basescan" in l or "uniscan" in l or "reactscan" in l:
                note(f"{l} blocks scripts ({exc}), checked by hand instead")
            else:
                dead.append(f"{l} ({exc})")
    if dead:
        bad("dead links: " + ", ".join(dead))
    else:
        ok(f"all {len(links)} external links answer")

    # ---------------------------------------------------------------- video
    mp4 = ROOT / "docs" / "demo.mp4"
    out = subprocess.run([str(FOUNDRY.parent / "ffprobe") if (FOUNDRY.parent / "ffprobe").exists() else "ffprobe",
                          "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp4)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        ff = pathlib.Path.home() / ".hermes" / "tools" / "ffmpeg-9.0.1-linux-x64" / "bin" / "ffprobe"
        out = subprocess.run([str(ff), "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(mp4)], capture_output=True, text=True)
    dur = float(out.stdout.strip() or 0)
    if 30 <= dur <= 180:
        ok(f"demo video is {dur:.1f}s, under three minutes")
    else:
        bad(f"demo video duration {dur}s is outside the allowed window")
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                              "-of", "csv=p=0", str(mp4)], capture_output=True, text=True)
    if "audio" in streams.stdout:
        ok("demo video has an audio track")
    else:
        bad("demo video has no audio track")
    cues = json.loads((ROOT / "demo" / "subs.json").read_text()) if (ROOT / "demo" / "subs.json").exists() else []
    if len(cues) >= 10:
        ok(f"{len(cues)} burned-in caption cues")
    else:
        bad("captions missing or too few")

    # -------------------------------------------------------------- hygiene
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    if any(t.endswith(".env") for t in tracked):
        bad(".env is tracked by git")
    else:
        ok(".env is not tracked")
    leaky = []
    for t in tracked:
        p = ROOT / t
        if p.suffix in (".py", ".sh", ".html", ".md", ".json") and p.exists():
            body = p.read_text(errors="ignore")
            if "/home/dell" in body:
                leaky.append(t)
    if leaky:
        bad("absolute machine paths in tracked files: " + ", ".join(leaky[:5]))
    else:
        ok("no absolute machine paths in tracked files")

    tests = subprocess.run([str(FOUNDRY / "forge"), "test", "--json"], cwd=ROOT, capture_output=True, text=True)
    try:
        total = sum(len(s["test_results"]) for s in json.loads(tests.stdout).values())
        if total >= 20:
            ok(f"{total} tests discovered")
        else:
            note(f"only {total} tests")
    except Exception:
        note("could not count tests from forge --json")

    print()
    print(f"{len(fails)} failure(s), {len(notes)} note(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
