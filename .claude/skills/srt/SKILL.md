---
name: srt
description: Export a video clip's audio to .mp3, transcribe it locally with Whisper, and write a Thai .srt subtitle file that follows the owner's subtitle rules (word-for-word, one line per cue, 1–2 second cues, continuous timecodes, Thai spacing only where it aids reading). Use whenever the user invokes /srt or asks to make subtitles, ซับ, ซับไตเติล, ถอดเสียง, SRT, or captions for a clip, an exported CapCut video, or footage on the NEABSSD project folders — even if they only say "ใส่ซับให้หน่อย" or attach/point to a video without naming the format.
---

# SRT — Thai subtitles from a clip

The owner's workflow: export the clip's audio as .mp3, transcribe it, and get a Thai .srt they can import into CapCut. Claude cannot listen to audio by itself, so transcription is done by the local Whisper model. Claude's job is to run it, then shape the result into the owner's exact SRT rules and catch mistakes the model makes.

## Owner's rules (verbatim intent — follow every one)

1. ถอดเสียงแบบคำต่อคำ ห้ามสรุป ห้ามแต่งประโยคใหม่ — word for word, no summarising, no rewriting. Keep spoken filler and interjections (เออ, อ่า, ครับ) because they carry the speaker's tone.
2. 1 Timecode มีข้อความ 1 บรรทัดเท่านั้น — exactly one text line per cue. Never put a line break inside a cue.
3. หั่นซับเป็นท่อนสั้น อ่านง่าย ประมาณ 1–2 วินาทีต่อท่อน — cut into short readable chunks of about 1–2 seconds. Break at natural pauses or phrase boundaries, never in the middle of a Thai word.
4. ใช้รูปแบบ .srt ให้ถูกต้อง: ลำดับ / Timecode / ข้อความ — standard SRT: index, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, text, blank line.
5. Timecode ต้องต่อเนื่องตามลำดับคลิป — timecodes run in order with no overlaps; each cue's end equals the next cue's start while speech continues. A real silence longer than ~0.7 s may stay as a gap.
6. ภาษาไทยไม่ต้องเว้นวรรคทุกคำ เว้นเฉพาะจุดที่อ่านง่าย — don't put a space between every Thai word; keep a space only where it helps reading (between phrases, around English words or numbers).

Output shape (the owner's example):

```
1
00:00:00,000 --> 00:00:01,500
ข้อความซับไตเติล

2
00:00:01,500 --> 00:00:03,000
ข้อความซับไตเติล
```

These rules sit inside the wider style guide (`style/VIDEO_EDITING_STYLE.md`, section "ซับไตเติลแบบคาราโอเกะ"): subtitles are required on every published clip, wrong or guessed words are not acceptable, and a failed transcription is never a reason to ship without subtitles.

## Workflow

### 1. Find the clip

Ask which clip if it isn't clear. Typical sources:
- A video exported from CapCut (in a project's `04_EXPORTS/` on the SSD, or `~/Movies`, `~/Downloads`).
- A camera original under `/Volumes/NEABSSD/Video_Projects/<project>/01_FOOTAGE/...`.

If the project lives on the SSD, check it is mounted (`ls /Volumes/NEABSSD`) before anything else.

### 2. Export the audio as .mp3

The owner wants the .mp3 kept as a deliverable. Inside a project folder, save it to `02_AUDIO/PROCESSED/<clip-name>.mp3`; otherwise save it next to the video.

**From a video file:**

```bash
ffmpeg -v error -y -i "<video>" -vn -ac 1 -ar 44100 -c:a libmp3lame -b:a 192k "<out>.mp3"
```

**From a CapCut project** (the usual case — the timeline mixes the hook audio with voiceovers the owner recorded in CapCut, which live only inside the draft): open the project in CapCut Desktop → **Export** → untick **Video** → tick **Audio**, Format **MP3** → set **Export to** the project's `02_AUDIO/PROCESSED/` → Export. This needs full-screen computer control. CapCut names the file `<project>.MP3` (upper-case extension).
- If a "Link media / Couldn't find some media" dialog appears on opening, check whether the missing file is on the timeline at all; unused media-pool items can be skipped with Cancel.

### 3. Transcribe with Whisper

Model: `~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin`. If it is missing, ask the owner before downloading it again (~550 MB, from `huggingface.co/ggerganov/whisper.cpp`).

Whisper reads 16 kHz mono WAV most reliably, so convert into the session scratchpad, then run with Thai forced and the full JSON (per-token timestamps):

```bash
ffmpeg -v error -y -i "<out>.mp3" -ar 16000 -ac 1 -c:a pcm_s16le "<scratch>/<clip>.wav"
whisper-cli -m ~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin \
  -l th -f "<scratch>/<clip>.wav" -ojf -of "<scratch>/<clip>"
```

This writes `<scratch>/<clip>.json`.

**Map where speech actually is** before trusting the output. Whisper invents text over silence, ambient noise and wind — in the first real test it produced 50 seconds of repeated "เกิดกับ…" and "ที่สุดที่สุด…" over a clip where speech was only in the first 11 seconds:

```bash
ffmpeg -i "<scratch>/<clip>.wav" -af silencedetect=n=-35dB:d=0.5 -f null - 2>&1 | grep -oE 'silence_(start|end): [0-9.]+'
```

Keep only cues inside the speech regions. Whisper's own timestamps also drift (it stretched 6.2–11.0 s of speech to 6.4–12.5 s), so use the silence boundaries to anchor where phrases start and end.

### 4. Build the draft SRT

```bash
python3 .claude/skills/srt/scripts/make_srt.py "<scratch>/<clip>.json" -o "<scratch>/<clip>.draft.srt"
```

The script groups Whisper's timed tokens into 1–2 s single-line cues, makes timecodes continuous, and removes spaces between Thai characters. Whisper's Thai tokens are often single characters, so the draft regularly cuts words in half (e.g. "กิโลก" / "รรม") — treat it as a timing reference, not the final text. To see where each word ends in time, print cumulative token text with each token's end offset from the JSON and pick cue boundaries at whole words. Options: `--min 1.0 --max 2.0` (cue length in seconds), `--gap 0.7` (silence that ends a cue and may stay as a gap), `--max-chars 24`.

### 5. Fix the draft by reading it — this step is not optional

Whisper and the grouping script both make mistakes the owner will see on screen. Read every cue and fix:

- **Broken Thai words** at cue boundaries (a vowel or tone mark split from its consonant, a word cut in half). Move the boundary to the nearest whole word and keep the timing continuous.
- **Proper nouns and product names** — check the project's `06_NOTES/` (e.g. `VOICEOVER_SCRIPT.md`) for spellings such as "Firemaple Tropic 2". Ask the owner when a name is unclear rather than guessing.
- **Hallucinations** — Whisper sometimes invents text during silence or music (e.g. "ขอบคุณที่รับชม", repeated lines). Delete cues with no matching speech.
- **Misheard Thai words** — Whisper confuses similar sounds (seen: เต้น for เต็นท์, เดิน for เต็นท์, คุม for คุ้ม, กิโลกรรม for กิโลกรัม, "ไฟล์ไม่เปิ้นทอปปิคทู" for "Firemaple Tropic 2"). Correct spelling when the intended word is clear from context; when a word could be something else, keep Whisper's version and flag it for the owner instead of guessing.
- **Spacing** — re-add a space only where it helps reading (rule 6).
- A voiceover script is a reference for spelling only. The subtitles follow what was actually said, word for word, even where the speaker went off-script (rule 1).

**Write the final cues as a plan, not by hand-typing timecodes.** Dump each Whisper segment's raw token text (`[_...]` tokens removed), drop zero-length segments (Whisper often emits a partial duplicate with `from == to` right before the real one), then write a `plan.py`:

```python
PLAN = [
  # (segment index, [(raw substring, corrected display text), ...])
  (0, [("และนี่ก็คือเต้นเดินป่า", "และนี่ก็คือเต็นท์เดินป่า"),
       ("ที่ราคาคุมค่ายที่สุดครับ", "ที่ราคาคุ้มค่าที่สุดครับ")]),
  (1, [("นั่นก็คือ ", "นั่นก็คือ"), ("5Mapel Topic 2 ครับ", "Firemaple Tropic 2 ครับ")]),
]
```

The raw pieces must rebuild the segment text exactly — they decide where each cue starts and ends in time; the display text is what appears on screen. Then:

```bash
python3 .claude/skills/srt/scripts/plan_to_srt.py "<scratch>/<clip>.json" "<scratch>/plan.py" -o "<scratch>/<clip>.srt"
```

It makes timecodes continuous, checks order, and warns about cues longer than ~2 s so you can split them at a word boundary.

Then check the file mechanically: numbering is 1..n, every cue is one line, start < end, each start ≥ the previous end.

### 6. Deliver

- Save the final file as `<clip-name>.srt` next to the .mp3's video source: in a project, `04_EXPORTS/<platform>/` when the source is an export, otherwise `06_NOTES/SUBTITLES/`.
- Show the owner the full SRT in chat (it is short) and point out every place you changed or were unsure of, so they can listen and confirm.
- To use it in CapCut Desktop: **Text → Local captions → Import file → the .srt**, hover the imported file and press **+** (CapCut places cues at their SRT timecodes). With a caption selected and **Apply to all** ticked: Bold, Preset style = white text with thick black outline, and a font size where the longest cue still fits on one line in 9:16 (15 worked; 18 wrapped "ไม่ว่าจะเป็นเต็นท์เดินป่าแคมปิง" mid-word). Check the longest cue in the preview.
- Karaoke highlight in CapCut is still unsolved — tell the owner rather than forcing it:
  - Text → Animation → search "karaoke" only offered a decorated variant (sakura flower), which breaks the style guide's "no distracting effects" rule, and animations apply one caption at a time.
  - Thai **Auto captions** + a **Word** caption template was tried and reverted: CapCut merged speech into multi-line paragraphs covering half the frame, broke Thai words across lines, and dropped phrases (e.g. the product name). Its text is still useful as a second opinion on words Whisper was unsure of.

Report honestly: if Whisper missed or garbled a section you could not resolve, say which timecodes, rather than filling them with plausible text.
