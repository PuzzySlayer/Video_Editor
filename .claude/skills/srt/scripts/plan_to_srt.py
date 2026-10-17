#!/usr/bin/env python3
"""Build the final SRT from a cue plan written by Claude.

The plan is a Python file defining PLAN = [(segment_index, [(raw, display), ...]), ...]
- segment_index: index into whisper JSON "transcription" (skip zero-length duplicates)
- raw: exact substrings of that segment's token text, in order; together they must
  rebuild the segment text exactly (this is how cue times are looked up)
- display: the corrected text shown on screen (fixed spelling, one line)

Cue start/end come from the first/last character's token offsets. Timecodes are made
continuous; silences of --gap seconds or more stay as gaps.

  python3 plan_to_srt.py clip.json plan.py -o clip.srt
"""
import argparse
import json
import runpy
import sys


def ts(ms):
    h, ms = divmod(int(ms), 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("json")
    p.add_argument("plan")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--gap", type=float, default=0.7)
    a = p.parse_args()

    segs = json.load(open(a.json, encoding="utf-8", errors="replace"))["transcription"]
    plan = runpy.run_path(a.plan)["PLAN"]
    cues = []
    for si, parts in plan:
        toks = [t for t in segs[si]["tokens"] if not t["text"].startswith("[_")]
        raw = "".join(t["text"] for t in toks)
        if "".join(r for r, _ in parts) != raw:
            sys.exit(f"segment {si}: raw pieces do not rebuild {raw!r}")
        times = []
        for t in toks:
            times += [(t["offsets"]["from"], t["offsets"]["to"])] * len(t["text"])
        pos = 0
        for r, disp in parts:
            cues.append([times[pos][0], times[pos + len(r) - 1][1], " ".join(disp.split())])
            pos += len(r)

    gap_ms = a.gap * 1000
    for x, y in zip(cues, cues[1:]):
        if y[0] - x[1] < gap_ms or x[1] > y[0]:
            x[1] = y[0]

    problems = []
    prev = 0
    for i, (s, e, t) in enumerate(cues, 1):
        if not s < e or s < prev:
            problems.append(f"cue {i} bad timing")
        if (e - s) > 2200:
            problems.append(f"cue {i} is {(e - s) / 1000:.2f}s (>2s) - consider splitting")
        prev = e

    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n" for i, (s, e, t) in enumerate(cues, 1)))
    print(f"{len(cues)} cues -> {a.out}", file=sys.stderr)
    for msg in problems:
        print("warning:", msg, file=sys.stderr)


if __name__ == "__main__":
    main()
