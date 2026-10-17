#!/usr/bin/env python3
"""Turn whisper.cpp full JSON (-ojf) into a Thai SRT draft.

Rules applied (see ../SKILL.md): one line per cue, ~1-2 s per cue,
continuous timecodes, no spaces between Thai characters.
The output is a draft: Claude still reads and fixes word breaks and names.
"""
import argparse
import json
import re
import sys

THAI = "฀-๿"
# Thai combining marks (vowels above/below, tone marks) that must never start a cue
THAI_MARKS = set(chr(c) for c in list(range(0x0E31, 0x0E32)) + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
# following vowels and repetition mark also can't open a cue
THAI_MARKS |= set("ะาำๆ")
SPECIAL = re.compile(r"^\[_.*_\]$|^\[.*\]$|^<\|.*\|>$")


def load_units(path):
    """Return [(text, start_s, end_s)] from token offsets, falling back to segments."""
    with open(path, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    units = []
    for seg in data.get("transcription", []):
        tokens = seg.get("tokens") or []
        seg_units = []
        for tok in tokens:
            text = tok.get("text", "")
            off = tok.get("offsets") or {}
            if not text or SPECIAL.match(text.strip()) or "from" not in off:
                continue
            seg_units.append([text, off["from"] / 1000.0, off["to"] / 1000.0])
        joined = "".join(u[0] for u in seg_units)
        if seg_units and "�" not in joined:
            units.extend(seg_units)
        else:
            # Token text can carry split UTF-8 bytes for Thai; use the segment instead.
            off = seg.get("offsets") or {}
            text = seg.get("text", "").strip()
            if text and "from" in off:
                units.append([text, off["from"] / 1000.0, off["to"] / 1000.0])
    return units


def clean(text):
    text = re.sub(r"\s+", " ", text).strip()
    # drop spaces between two Thai characters; keep them around Latin words/numbers
    return re.sub(rf"(?<=[{THAI}]) (?=[{THAI}])", "", text)


def group(units, min_d, max_d, gap, max_chars):
    cues = []
    cur = None
    for text, t0, t1 in units:
        if cur is not None:
            silence = t0 - cur["end"]
            dur = t1 - cur["start"]
            starts_with_mark = text.lstrip()[:1] in THAI_MARKS
            too_long = dur > max_d or len(clean(cur["text"] + text)) > max_chars
            if not starts_with_mark and (silence >= gap or (too_long and cur["end"] - cur["start"] >= min_d * 0.5)):
                cues.append(cur)
                cur = None
        if cur is None:
            cur = {"text": text, "start": t0, "end": t1}
        else:
            cur["text"] += text
            cur["end"] = t1
    if cur:
        cues.append(cur)

    # continuous timecodes: close small gaps, keep real silences
    for a, b in zip(cues, cues[1:]):
        if b["start"] - a["end"] < gap:
            a["end"] = b["start"]
        if a["end"] > b["start"]:
            a["end"] = b["start"]
    out = []
    for c in cues:
        text = clean(c["text"])
        if text and c["end"] > c["start"]:
            out.append((c["start"], c["end"], text))
    return out


def ts(s):
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("json")
    p.add_argument("-o", "--out", help="output .srt (default: stdout)")
    p.add_argument("--min", type=float, default=1.0, help="target minimum cue length (s)")
    p.add_argument("--max", type=float, default=2.0, help="maximum cue length (s)")
    p.add_argument("--gap", type=float, default=0.7, help="silence that ends a cue and stays as a gap (s)")
    p.add_argument("--max-chars", type=int, default=24)
    a = p.parse_args()

    cues = group(load_units(a.json), a.min, a.max, a.gap, a.max_chars)
    srt = "\n".join(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n" for i, (s, e, t) in enumerate(cues, 1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(srt)
        print(f"{len(cues)} cues -> {a.out}", file=sys.stderr)
    else:
        sys.stdout.write(srt)


if __name__ == "__main__":
    main()
