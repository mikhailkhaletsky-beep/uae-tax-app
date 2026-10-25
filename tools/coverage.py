"""Rough completeness check: share of 6-word shingles of the source text that survive in the parsed text."""
import os, re, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M, textparse as T

acts, docs = M.build_all()


def words(s):
    s = T.strip_arabic(s)
    return re.findall(r"[A-Za-z0-9%]+", s.lower())


for a in T and M.A.ACTS:
    for ed in a["editions"]:
        if ed.get("tables_only"):
            continue
        path = M.edition_text_path(ed)
        raw_lines = []
        for pg in T.load_lines(path):
            kept, _ = T.split_footnotes(pg)
            raw_lines += [l for l in kept if not T.is_noise(l)]
        raw = words(" ".join(raw_lines))
        d = docs[(a["id"], ed["id"])]
        parts = [M.block_plain(b) for b in d["pre"]]
        for s in d["sections"]:
            if s["type"] == "chapter":
                parts.append(s["label"] + " " + s["title"])
                parts += [M.block_plain(b) for b in s.get("blocks", [])]
            else:
                parts.append("Article " + s["num"] + " " + s["title"])
                parts += [M.block_plain(b) for b in s["blocks"]]
        have = words(" ".join(parts))
        K = 6
        sh = lambda w: {tuple(w[i:i + K]) for i in range(len(w) - K + 1)}
        rs, hs = sh(raw), sh(have)
        cov = len(rs & hs) / max(1, len(rs))
        extra = len(hs - rs) / max(1, len(hs))
        flag = "  <-- check" if cov < 0.97 else ""
        print(f"{a['id']:6} {ed['id']:16} source_words={len(raw):6} parsed_words={len(have):6} coverage={cov:6.1%} extra={extra:5.1%}{flag}")

if len(sys.argv) > 1:
    aid, eid = sys.argv[1], sys.argv[2]
    a = next(x for x in M.A.ACTS if x["id"] == aid)
    ed = next(e for e in a["editions"] if e["id"] == eid)
    path = M.edition_text_path(ed)
    raw_lines = []
    for pg in T.load_lines(path):
        kept, _ = T.split_footnotes(pg)
        raw_lines += [l for l in kept if not T.is_noise(l)]
    raw = words(" ".join(raw_lines))
    d = docs[(aid, eid)]
    parts = [M.block_plain(b) for b in d["pre"]]
    for s in d["sections"]:
        if s["type"] == "chapter":
            parts.append(s["label"] + " " + s["title"])
        else:
            parts.append("Article " + s["num"] + " " + s["title"])
            parts += [M.block_plain(b) for b in s["blocks"]]
    have = words(" ".join(parts))
    K = 6
    hs = {tuple(have[i:i + K]) for i in range(len(have) - K + 1)}
    miss = [i for i in range(len(raw) - K + 1) if tuple(raw[i:i + K]) not in hs]
    shown = 0; last = -99
    for i in miss:
        if i - last > 8 and shown < 12:
            print("MISSING near:", " ".join(raw[max(0, i - 3):i + 12])); shown += 1
        last = i
