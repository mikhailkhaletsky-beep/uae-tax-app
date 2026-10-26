#!/usr/bin/env python3
"""Parse every guide / Public Clarification PDF into sources/parsed/<key>.json (slow; the build reuses the result).

Usage:  python3 tools/parse_guides.py [key ...] [-f]     (-f: parse again even when the cache is up to date)
"""
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acts_data as A  # noqa: E402
import model as M  # noqa: E402


def job(args):
    ed, force = args
    if force:
        c = os.path.join(M.PARSED_DIR, ed["src"] + ".json")
        if os.path.exists(c):
            os.remove(c)
    g = M.guide_blocks(ed)
    n = sum(1 for b in g["blocks"] if b["kind"] == "heading")
    return ed["src"], g["pages"], n, len(g["notes"]), len(g["blocks"])


if __name__ == "__main__":
    force = "-f" in sys.argv
    keys = [x for x in sys.argv[1:] if x != "-f"]
    eds = [e for a in A.ACTS for e in a["editions"] if e.get("fmt") == "guide" and (not keys or e["src"] in keys)]
    eds.sort(key=lambda e: -os.path.getsize(os.path.join(M.PDF_DIR, e["src"] + ".pdf")))
    with Pool(3) as pl:
        for r in pl.imap_unordered(job, [(e, force) for e in eds]):
            print(*r, flush=True)
