#!/usr/bin/env python3
"""Build the narration track and the subtitle cues from the per-sentence clips.

Writes demo/narration2.wav, demo/subs.srt and demo/subs.json. No libass needed: the film renders
each cue as a transparent strip and overlays it with an enable window.
"""
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
LEAD = 0.7
GAP = 0.30

LINES = [
    "Two venues trade the same pair. One on Base Sepolia, one on Unichain.",
    "When they disagree, someone gets hurt.",
    "Second Guard is a reactive contract on Reactive Lasna. It watches a swap on both chains, holds both prices in its own state, and measures the gap.",
    "Here is the attack. A single dump pushes the Base venue thirty two percent away from its twin.",
    "One event, two callbacks. The rule fires in the same second, and both venues stop.",
    "The gap was twenty seven hundred basis points. The guard recorded the source block, and both chains carry the same number.",
    "No keeper. No relayer. No off chain watcher. Just one rule, living on chain, measured end to end in under two seconds.",
]


def probe(path):
    return float(
        subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    )


def ts(seconds):
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def main():
    clips = [DEMO / f"vo{i}.mp3" for i in range(1, len(LINES) + 1)]
    durs = [probe(c) for c in clips]

    cues, t = [], LEAD
    for line, dur in zip(LINES, durs):
        # split a clip into sentence cues so no caption sits on screen for ten seconds
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
        weights = [max(len(s), 12) for s in parts]
        span = dur - 0.08 * (len(parts) - 1)
        for part, w in zip(parts, weights):
            share = span * w / sum(weights)
            cues.append({"start": round(t, 3), "end": round(t + share, 3), "text": part})
            t += share + 0.08
        t += GAP
    total = t

    # audio: lead-in silence, then each clip at its cue start, summed
    inputs, filters, labels = [], [], []
    for i, (clip, cue) in enumerate(zip(clips, cues)):
        inputs += ["-i", str(clip)]
        delay = int(cue["start"] * 1000)
        filters.append(f"[{i}:a]aresample=48000,adelay={delay}|{delay}[a{i}]")
        labels.append(f"[a{i}]")
    fc = ";".join(filters) + ";" + "".join(labels) + f"amix=inputs={len(clips)}:normalize=0,apad=whole_dur={total}[out]"
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
         "-ac", "1", "-ar", "48000", str(DEMO / "narration2.wav")],
        check=True,
    )

    (DEMO / "subs.json").write_text(json.dumps(cues, indent=1))
    srt = []
    for i, c in enumerate(cues, 1):
        srt.append(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n")
    (DEMO / "subs.srt").write_text("\n".join(srt))

    print(json.dumps({"clips": len(clips), "total": round(total, 2), "audio": probe(DEMO / "narration2.wav")}, indent=1))


if __name__ == "__main__":
    main()
