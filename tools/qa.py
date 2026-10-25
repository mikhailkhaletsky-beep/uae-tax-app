"""Quality checks for the parsed editions. Run: python3 tools/qa.py"""
import re
import sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import model as M

acts, docs = M.build_all()
problems = 0
for (aid, eid), d in docs.items():
    arts = [s for s in d["sections"] if s["type"] == "article"]
    nums = []
    for s in arts:
        m = re.match(r"^(\d+)$|^(\d+) bis$", s["num"])
        if m:
            nums.append(int(m.group(1) or m.group(2)))
    gaps = [n for n in range(1, (max(nums) if nums else 0) + 1) if n not in nums]
    dup = sorted({s["num"] for s in arts if sum(1 for t in arts if t["num"] == s["num"]) > 1})
    empty = [s["num"] for s in arts if not s["blocks"]]
    arabic = sum(1 for s in arts for b in s["blocks"] if b["kind"] == "p" and re.search(r"[؀-ۿ]", b["text"]))
    longp = [s["num"] for s in arts for b in s["blocks"] if b["kind"] == "p" and len(b["text"]) > 2500]
    headinp = [s["num"] for s in arts for b in s["blocks"] if b["kind"] == "p" and re.search(r"(?:^|\s)Article \(?\d+\)?\s*$", b["text"])]
    footer = [s["num"] for s in arts for b in s["blocks"] if b["kind"] == "p" and re.search(r"Unofficial|As published|Page \d+", b["text"])]
    flags = []
    if gaps: flags.append(f"gaps={gaps[:12]}")
    if dup: flags.append(f"dup={dup[:12]}")
    if empty: flags.append(f"empty={empty[:12]}")
    if arabic: flags.append(f"arabic_in_p={arabic}")
    if longp: flags.append(f"longp={longp[:8]}")
    if headinp: flags.append(f"heading_in_p={headinp[:8]}")
    if footer: flags.append(f"footer_leak={footer[:8]}")
    if d["leftover"]: flags.append(f"unplaced_notes={sorted(d['leftover'], key=int)}")
    status = "OK " if not flags else "!! "
    problems += bool(flags)
    print(status, aid, eid, f"arts={len(arts)}", " ".join(flags))
print("editions with flags:", problems)
