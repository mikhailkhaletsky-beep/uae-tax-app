"""Turn `pdftotext -layout` output of an English legal text into structured blocks.

Block kinds
    chapter   {"label": "Chapter One", "title": "General provisions", "id": "ch-1"}
    article   {"num": "12", "title": "...", "id": "art-12"}
    p         {"text": "...", "level": 0, "marker": "1."}
    defs      {"rows": [(term, text), ...]}
    pre       {"text": "..."}          (tables / schedules kept in layout form)
    pre-start handled internally

The parser never drops legal text: anything it cannot classify becomes a plain paragraph.
"""
import os
import re
import unicodedata

ARABIC = re.compile(r"[֐-ࣿיִ-﷿ﹰ-﻿‎‏‪-‮⁦-⁩]")

NOISE = [
    re.compile(r"^\s*(?:Page\s*)?\d{1,3}\s*(?:\|\s*Page)?\s*$", re.I),
    re.compile(r"^\s*\d{1,3}\s*\|\s*Page\s*$", re.I),
    re.compile(r"This is not an official Translation:?", re.I),
    re.compile(r"Unofficial Translation\s*\d*\s*$", re.I),
    re.compile(r"As published (?:by|in) (?:the )?(?:Ministry of Finance|Official Gazette)\s*\d*\s*$", re.I),
    re.compile(r"^\s*The English section is an unofficial translation\s*$", re.I),
    re.compile(r"^\s*\(as published by the Ministry of Finance\)\s*$", re.I),
    re.compile(r"and its amendments\s*[–-]\s*Unofficial translation\s*\d*\s*$", re.I),
    re.compile(r"^\s*List of Qualifying Public Benefit Entities\s+\d+\s*$", re.I),
]
RE_INLINE_FN = re.compile(r"^\s{0,14}(\d{1,2})\s+((?:Definition|Clause|Article|Paragraph|Text|Item|Sub-?clause)\b.{5,})$")

NUM = r"\d+(?:\.\d+)*(?:\s*bis)?"
RE_CHAPTER = re.compile(r"^\s*(Chapter|Part|Section|Book|Title)\s+([A-Za-z0-9.]+)\s*(?:[–—-]\s*(.*))?$")
RE_ART_DASH = re.compile(r"^\s{0,16}Article\s+(" + NUM + r")\s*[.:]?\s*[–—-]\s*(\S.{0,110})$")
WORDNUM = {w: i + 1 for i, w in enumerate("One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen Twenty".split())}
RE_ART_DASHC = re.compile(r"^\s{17,70}Article\s+(" + NUM + r")\s*[.:]?\s*[–—-]\s*(\S.{0,110})$")
RE_ART_WORD = re.compile(r"^\s{6,}Article\s+(" + "|".join(WORDNUM) + r")\s*$")
RE_ART_BISALONE = re.compile(r"^\s{0,16}Article\s+(\d+)\s*\(?bis\)?\s*(\d{1,2})?\s*$", re.I)
RE_ART_BIS = re.compile(r"^\s{0,16}Article\s*\(?(\d+)\)?\s*bis\s*[–—-]\s*(\S.{0,110})$", re.I)
RE_ART_OPEN = re.compile(r"^\s{0,60}Article\s+(" + NUM + r")\s*[–—-]\s*$")
RE_ART_DOT = re.compile(r"^\s{0,12}Article\s+(\d+\.\d+(?:\.\d+)*)\.?\s+([A-Z][^.]{2,100})$")
RE_ART_ALONE = re.compile(r"^\s*Article\s*\(?\s*(" + NUM + r")\s*\)?\s*$")

def looks_article(line):
    for rx in (RE_ART_DASH, RE_ART_DASHC, RE_ART_OPEN, RE_ART_BIS, RE_ART_BISALONE, RE_ART_WORD, RE_ART_DOT, RE_ART_ALONE):
        if rx.match(line):
            return True
    return False


RE_MARK_DEC = re.compile(r"^(\d+(?:\.\d+){1,5})\.?\s+(?=\S)")
RE_MARK_NUM = re.compile(r"^(\d{1,3})\.\s+(?=\S)")
RE_MARK_NUMP = re.compile(r"^\((\d{1,3})\)\s+(?=\S)")
RE_MARK_NUMR = re.compile(r"^(\d{1,2})\)\s+(?=\S)")
RE_MARK_ALPHA = re.compile(r"^\(?([a-z])[.)]\s+(?=\S)")
RE_MARK_ROMAN = re.compile(r"^\(?((?:ix|iv|v?i{1,3}|x{1,2}))[.)]\s+(?=\S)")
RE_MARK_BUL = re.compile(r"^([-–•·])\s+(?=\S)")

RE_DEF = re.compile(r"^(?P<ind>\s*)(?P<term>[A-Z“\"‘'][^:]{0,90}?)\s*:\s+(?P<def>\S.*)$")
RE_DEF_TERM_ONLY = re.compile(r"^(?P<term>[A-Z“\"‘'][^:]{0,60}?)\s*:\s*$")
RE_TERM_WRAP = re.compile(r"^(?P<left>\S[^\s]*(?: \S+){0,2})\s{3,}(?P<right>\S.*)$")

TABLE_START = re.compile(
    r"^\s*(Table of .*|List of .*|Schedule\b.*|Annex(?:ure)?\b.*|Appendix\b.*|Table\s+\d+.*)$", re.I
)


ARABIC_START = re.compile("[\u0600-\u06ff\u202b\u202c\u200f\u061c\ufb50-\ufdff\ufe70-\ufeff]")


def strip_arabic(s: str) -> str:
    return ARABIC.sub("", s)


def load_lines(path: str, drop_arabic: bool = True):
    """Return list of pages, each a list of raw lines (rstrip'd)."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    crop_mode = ".crop." in os.path.basename(path)
    pages = raw.split("\f")
    out = []
    for pg in pages:
        lines = []
        for ln in pg.splitlines():
            if drop_arabic:
                if crop_mode:
                    # bilingual list cropped to the English column: whatever follows the first Arabic mark is the other column
                    mm = ARABIC_START.search(ln)
                    if mm:
                        ln = ln[:mm.start()]
                ln = strip_arabic(ln)
            ln = unicodedata.normalize("NFC", ln.replace(" ", " ").replace("​", ""))
            ln = ln.rstrip()
            lines.append(ln)
        out.append(lines)
    return out


def is_noise(ln: str) -> bool:
    return any(p.search(ln) for p in NOISE)


def split_footnotes(lines):
    """Pull footnotes (bare number line followed by text) out of a page. Returns (body, {num: text})."""
    body, notes = [], {}
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        mi = RE_INLINE_FN.match(ln)
        if mi and re.search(r"\b(as per|amended|added|replaced|repealed)\b", mi.group(2)):
            base_ind = indent_of(ln)
            parts = [mi.group(2).strip()]
            j = i + 1
            while j < n and lines[j].strip() and indent_of(lines[j]) >= base_ind and not RE_INLINE_FN.match(lines[j]):
                parts.append(lines[j].strip())
                j += 1
            # a footnote can continue after a blank line (text split across the page bottom)
            k = j
            while k < n and not lines[k].strip():
                k += 1
            while k < n and lines[k].strip() and not is_noise(lines[k]) and not RE_INLINE_FN.match(lines[k]) \
                    and indent_of(lines[k]) >= base_ind and lines[k].strip()[:1].islower():
                parts.append(lines[k].strip())
                k += 1
                j = k
            notes[mi.group(1)] = re.sub(r"\s+", " ", " ".join(parts))
            i = j
            continue
        if re.fullmatch(r"\d{1,2}", ln.strip()) and indent_of(ln) < 6 and i + 1 < n and lines[i + 1].strip() \
                and indent_of(lines[i + 1]) < 8 and not re.fullmatch(r"\d{1,2}", lines[i + 1].strip()):
            num = ln.strip()
            j = i + 1
            parts = []
            while j < n and lines[j].strip() and not (re.fullmatch(r"\d{1,2}", lines[j].strip()) and indent_of(lines[j]) < 6):
                parts.append(lines[j].strip())
                j += 1
            notes[num] = re.sub(r"\s+", " ", " ".join(parts))
            i = j
            continue
        body.append(ln)
        i += 1
    return body, notes


def drop_footer_pairs(lines):
    out, i = [], 0
    while i < len(lines):
        if re.match(r"^\s*Federal Decree-Law of 2023 Amending Certain Provisions", lines[i]):
            i += 1
            if i < len(lines) and re.match(r"^\s*and Businesses\s*$", lines[i]):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def flatten(pages, want_notes=False):
    """Remove headers/footers and footnotes; keep a blank line at page boundaries."""
    flat, notes = [], {}
    for pg in pages:
        kept, nts = split_footnotes(pg)
        kept = [ln for ln in kept if not is_noise(ln)]
        kept = drop_footer_pairs(kept)
        for k, v in nts.items():
            notes.setdefault(k, v)
        while kept and not kept[0].strip():
            kept.pop(0)
        while kept and not kept[-1].strip():
            kept.pop()
        flat.extend(kept)
        flat.append("\f")
    return (flat, notes) if want_notes else flat


def indent_of(ln: str) -> int:
    return len(ln) - len(ln.lstrip(" "))


def marker_of(text: str):
    """Return (marker, level, rest) or None."""
    m = RE_MARK_DEC.match(text)
    if m:
        return m.group(1), min(m.group(1).count(".") , 4), text[m.end():]
    m = RE_MARK_NUM.match(text)
    if m:
        return m.group(1) + ".", 0, text[m.end():]
    m = RE_MARK_NUMP.match(text)
    if m:
        return "(" + m.group(1) + ")", 0, text[m.end():]
    m = RE_MARK_NUMR.match(text)
    if m:
        return m.group(1) + ")", 2, text[m.end():]
    m = RE_MARK_ROMAN.match(text)
    if m and len(m.group(1)) > 1:
        return m.group(0).strip().split()[0], 2, text[m.end():]
    m = RE_MARK_ALPHA.match(text)
    if m:
        return m.group(0).strip().split()[0], 1, text[m.end():]
    m = RE_MARK_BUL.match(text)
    if m:
        return m.group(1), 1, text[m.end():]
    return None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Parser:
    def __init__(self, lines, table_start=None):
        self.lines = lines
        self.blocks = []
        self.cur = None  # current paragraph dict
        self.used_ids = set()
        self.in_defs = False
        self.defs_rows = None
        self.in_pre = False
        self.pre_lines = []
        self.table_start = re.compile(table_start, re.I) if table_start else TABLE_START
        self.last_blank = True
        self.last_pb = False
        self.art_seen = False

    # -- helpers
    def uid(self, base):
        i, cand = 2, base
        while cand in self.used_ids:
            cand = f"{base}-{i}"
            i += 1
        self.used_ids.add(cand)
        return cand

    def flush_p(self):
        if self.cur:
            self.cur["text"] = re.sub(r"\s+", " ", self.cur["text"]).strip()
            if self.cur["text"] or self.cur.get("marker"):
                self.blocks.append(self.cur)
            self.cur = None

    def flush_defs(self):
        if self.defs_rows:
            rows = [(re.sub(r"\s+", " ", t).strip(), re.sub(r"\s+", " ", d).strip()) for t, d in self.defs_rows]
            self.blocks.append({"kind": "defs", "rows": rows})
        self.defs_rows = None
        self.in_defs = False

    def flush_pre(self):
        if self.pre_lines:
            while self.pre_lines and not self.pre_lines[-1].strip():
                self.pre_lines.pop()
            while self.pre_lines and not self.pre_lines[0].strip():
                self.pre_lines.pop(0)
            if self.pre_lines:
                ind = min(indent_of(l) for l in self.pre_lines if l.strip())
                txt = "\n".join(l[ind:] for l in self.pre_lines)
                self.blocks.append({"kind": "pre", "text": txt})
        self.pre_lines = []
        self.in_pre = False

    @staticmethod
    def join_text(a, b):
        if a.endswith("-") and b[:1].isalpha():
            return a + b
        return a + " " + b

    def add_text(self, text):
        if self.cur is None:
            self.cur = {"kind": "p", "text": text, "level": 0, "marker": ""}
        else:
            if self.cur["text"].endswith("-") and text[:1].isalpha():
                self.cur["text"] += text
            else:
                self.cur["text"] += " " + text

    # -- main loop
    def run(self):
        L = self.lines
        n = len(L)
        i = 0
        while i < n:
            ln = L[i]
            st = ln.strip()
            if not st:
                self.last_blank = True
                self.last_pb = self.last_pb or ln == "\f"
                if self.in_pre:
                    self.pre_lines.append("")
                i += 1
                continue
            blank_before = self.last_blank
            pb_before = self.last_pb
            self.last_blank = False
            self.last_pb = False

            # ---------- chapter
            m = RE_CHAPTER.match(ln)
            prev_is_chapter = bool(self.blocks) and self.blocks[-1].get("kind") == "chapter"
            if m and indent_of(ln) < 20 and len(st) < 130 and (blank_before or prev_is_chapter) and (m.group(3) or "").strip() != "" and not st.endswith(","):
                title = m.group(3).strip()
                # wrapped title on following line(s)
                j = i + 1
                while j < n and L[j].strip() and indent_of(L[j]) < 20 and not RE_ART_DASH.match(L[j]) \
                        and not RE_CHAPTER.match(L[j]) and not title.endswith((".", ":")) and len(L[j].strip()) < 90 \
                        and L[j].strip()[:1].islower() | L[j].strip()[:1].isupper() and not marker_of(L[j].strip()):
                    # only join when the previous line clearly continues (no end punctuation, next starts lower-case or is short)
                    if L[j].strip()[:1].islower() or len(title) > 55:
                        title += " " + L[j].strip()
                        j += 1
                    else:
                        break
                # a short capitalised line that sits directly before an article heading also continues the title
                if j < n and L[j].strip() and indent_of(L[j]) < 20 and len(L[j].strip()) < 70 and not title.endswith((".", ":")) \
                        and not L[j].strip().endswith((".", ":", ";")) and not marker_of(L[j].strip()) and not RE_CHAPTER.match(L[j]) \
                        and not looks_article(L[j]):
                    k = j + 1
                    while k < n and not L[k].strip():
                        k += 1
                    if k < n and looks_article(L[k]):
                        title += " " + L[j].strip()
                        j += 1
                self.close_all()
                label = f"{m.group(1)} {m.group(2)}"
                self.blocks.append({"kind": "chapter", "label": label, "title": title, "id": self.uid(slug(label))})
                i = j
                continue

            # ---------- article headings
            num = title = None
            label_override = None
            m = RE_ART_DASH.match(ln) or RE_ART_DASHC.match(ln)
            mo = RE_ART_OPEN.match(ln)
            mb = RE_ART_BIS.match(ln)
            mba = RE_ART_BISALONE.match(ln)
            mw = RE_ART_WORD.match(ln)
            if mw:
                num, title = str(WORDNUM[mw.group(1)]), ""
                label_override = "Article " + mw.group(1)
            elif mb:
                num, title = mb.group(1) + " bis", mb.group(2).strip()
            elif mba:
                num, title = mba.group(1) + " bis", (mba.group(2) or "")
            elif mo and i + 1 < n:
                j = i + 1
                while j < n and not L[j].strip():
                    j += 1
                num = mo.group(1)
                title = L[j].strip() if j < n else ""
                i = j
            elif m:
                num, title = m.group(1), m.group(2).strip()
                # wrapped title
                j = i + 1
                while j < n and L[j].strip() and indent_of(L[j]) < 20 and not title.endswith((".", ":", ";")) \
                        and len(L[j].strip()) < 70 and L[j].strip()[:1].islower() and not marker_of(L[j].strip()):
                    title += " " + L[j].strip()
                    j += 1
                i = j - 1
            if num is None:
                m = RE_ART_DOT.match(ln)
                prev_art = bool(self.blocks) and self.blocks[-1].get("kind") == "article" and self.cur is None
                if m and (blank_before or prev_art):
                    num, title = m.group(1), m.group(2).strip()
                    j = i + 1
                    while j < n and L[j].strip() and indent_of(L[j]) < 14 and len(L[j].strip()) < 80 and not marker_of(L[j].strip()) \
                            and not looks_article(L[j]) and not RE_CHAPTER.match(L[j]) and not title.endswith((".", ":")):
                        title += " " + L[j].strip()
                        j += 1
                    i = j - 1
            if num is None:
                m = RE_ART_ALONE.match(ln)
                if m and (blank_before or indent_of(ln) >= 6) and indent_of(ln) >= 6:
                    num = m.group(1)
                    j = i + 1
                    tparts = []
                    k = j
                    while k < n and not L[k].strip() and k - j < 2:
                        k += 1
                    if k > j and k < n and L[k].strip() and indent_of(L[k]) >= 20 and len(L[k].strip()) < 90 and not marker_of(L[k].strip()) \
                            and not looks_article(L[k]):
                        j = k
                    while j < n and L[j].strip() and indent_of(L[j]) >= 10 and not marker_of(L[j].strip()) and len(tparts) < 3:
                        tparts.append(L[j].strip())
                        j += 1
                    if not tparts:
                        # a long title set flush left: one standalone line without a final stop, optionally wrapped onto short lines
                        k = j
                        while k < n and not L[k].strip() and k - j < 2:
                            k += 1
                        if k < n:
                            def _title_line(x):
                                return x and not x.endswith((".", ":", ";", ",")) and x[:1].isupper() and not marker_of(x) \
                                    and not looks_article(x) and not RE_CHAPTER.match(x)
                            def _ends_title(x):               # blank line or the first marker of the body follows
                                return x >= n or not L[x].strip() or bool(marker_of(L[x].strip()))
                            grp, q = [], k
                            while q < n and L[q].strip() and len(grp) < 3 and len(L[q].strip()) <= 140 and (_title_line(L[q].strip()) or (grp and not L[q].strip().endswith(".") and not marker_of(L[q].strip()))):
                                grp.append(L[q].strip())
                                q += 1
                            if grp and _ends_title(q) and (len(grp) == 1 or all(not g.endswith(".") for g in grp)):
                                tparts = grp
                                j = q
                    title = " ".join(tparts)
                    i = j - 1
                elif m and indent_of(ln) < 6 and len(st) < 25:
                    num = m.group(1)
                    j = i + 1
                    title = ""
                    if j < n and L[j].strip() and len(L[j].strip()) < 90 and not marker_of(L[j].strip()) and L[j].strip()[:1].isupper():
                        title = L[j].strip()
                        i = j
            if num is not None:
                label = label_override
                self.close_all()
                num = re.sub(r"\s+", " ", num).strip()
                title = (title or "").strip().rstrip(",")
                aid = self.uid("art-" + slug(num))
                blk = {"kind": "article", "num": num, "title": title or "", "id": aid}
                if label:
                    blk["label"] = label
                self.blocks.append(blk)
                self.art_seen = True
                self.in_defs = bool(re.search(r"definition", title or "", re.I))
                self.defs_rows = None
                i += 1
                continue

            # ---------- table / schedule start
            if not self.in_pre and indent_of(ln) < 40 and len(st) < 140 and self.table_start.match(ln) and blank_before:
                # require that following lines look columnar
                look = [x for x in L[i + 1:i + 14] if x.strip()]
                colish = sum(1 for x in look if re.search(r"\S {3,}\S", x))
                if colish >= 3:
                    self.close_all()
                    self.blocks.append({"kind": "p", "text": st, "level": 0, "marker": "", "strong": True})
                    self.in_pre = True
                    self.pre_lines = []
                    i += 1
                    continue
            if self.in_pre:
                self.pre_lines.append(ln)
                i += 1
                continue

            # ---------- definitions
            if self.in_defs:
                md = RE_DEF.match(ln)
                term_ok = False
                if md:
                    term = md.group("term").strip()
                    words = term.split()
                    term_ok = len(words) <= 9 and not term.endswith((".", ",", ";")) and not term.lower().startswith(("article", "pursuant", "having"))
                if term_ok and (self.defs_rows is not None or blank_before or True):
                    if self.defs_rows is None:
                        self.flush_p()
                        self.defs_rows = []
                    self.defs_rows.append([term, md.group("def").strip()])
                    self.def_col = md.start("def")
                    i += 1
                    continue
                if self.defs_rows is not None:
                    # continuation of a definition
                    stripped = ln.lstrip()
                    ind = indent_of(ln)
                    mt = re.match(r"^(\S[^\s]*(?: \S+){0,2})\s{3,}(\S.*)$", stripped)
                    dc = getattr(self, "def_col", 20)
                    if mt and len(mt.group(1)) <= 30 and ind < dc - 6 and dc > 14 and not blank_before:
                        self.defs_rows[-1][0] += " " + mt.group(1)
                        self.defs_rows[-1][1] = self.join_text(self.defs_rows[-1][1], mt.group(2).strip())
                    elif blank_before and ind < 6 and not RE_DEF.match(ln) and (st[:1].isupper() or marker_of(st)) \
                            and (dc <= 14 or ind < dc - 6):
                        # new paragraph after the table of definitions
                        self.flush_defs()
                        self.in_defs = False
                        continue
                    else:
                        self.defs_rows[-1][1] = self.join_text(self.defs_rows[-1][1], st)
                    i += 1
                    continue

            # ---------- ordinary paragraph text
            mk = marker_of(st)
            if mk:
                self.flush_p()
                marker, level, rest = mk
                self.cur = {"kind": "p", "text": rest, "level": level, "marker": marker}
                if pb_before:
                    self.cur["pb"] = True
                i += 1
                continue
            if self.cur is not None and blank_before:
                prev = self.cur["text"].rstrip()
                if prev and ((prev[-1] not in ".:;)”\"’!?" and st[:1].islower())
                             or (pb_before and prev[-1] not in ".:;”\"’!?" and not self.cur.get("strong"))):
                    self.add_text(st)
                    i += 1
                    continue
                # a blank line separates paragraphs; keep list items together with their wrapped text
                self.flush_p()
                self.cur = {"kind": "p", "text": st, "level": 0, "marker": ""}
                if pb_before:
                    self.cur["pb"] = True
                i += 1
                continue
            self.add_text(st)
            i += 1
        self.close_all()
        return self.blocks

    def close_all(self):
        self.flush_p()
        self.flush_defs()
        self.flush_pre()


def parse_file(path, table_start=None, want_notes=False):
    pages = load_lines(path)
    lines, notes = flatten(pages, want_notes=True)
    blocks = Parser(lines, table_start).run()
    return (blocks, notes) if want_notes else blocks


if __name__ == "__main__":
    import sys, collections
    for p in sys.argv[1:]:
        b = parse_file(p)
        c = collections.Counter(x["kind"] for x in b)
        arts = [x["num"] for x in b if x["kind"] == "article"]
        print(p.split("/")[-1], dict(c), "articles:", arts[:8], "...", arts[-3:])


# ---------------------------------------------------------------------------
# Entity lists (e.g. Cabinet Decision 37/2023 annex): "No.  Entity name   To   From"
RE_ROW = re.compile(
    r"^\s*(\d{1,4})\.\s+(?P<name>.+?)\s{2,}(?P<to>[–-]|\d{2}/\d{2}/\d{4})\s+(?P<frm>[–-]|\d{2}/\d{2}/\d{4})(?:\s+.*)?$"
)
RE_SECTION = re.compile(r"^\s*No\.\s+(?P<title>[A-Za-z][A-Za-z ]+?Entities)\s*(?:\s{2,}Effective\b.*)?$")
RE_FN_LINE = re.compile(r"^\s{0,12}(\d{1,3})\s+(?P<t>[A-Z(].{8,})$")


def parse_entity_table(text):
    """Return list of {"title": str, "rows": [[no, name, to, from, fn]], "notes": {n: text}} or None."""
    sections, cur, last, fn_open = [], None, None, None
    notes = {}
    for ln in text.splitlines():
        if not ln.strip():
            continue
        ms = RE_SECTION.match(ln)
        if ms:
            title = ms.group("title").strip()
            if cur is None or cur["title"] != title:
                cur = {"title": title, "rows": []}
                sections.append(cur)
            last, fn_open = None, None
            continue
        if re.match(r"^\s*(To\s+From|Effective|From\s+To|To|From|Effective\s+To\s+From)\s*$", ln.strip()):
            continue
        mr = RE_ROW.match(ln)
        if mr and cur is not None:
            name = re.sub(r"\s+", " ", mr.group("name")).strip()
            row = [mr.group(1), name, mr.group("to"), mr.group("frm"), ""]
            cur["rows"].append(row)
            last, fn_open = row, None
            continue
        mf = RE_FN_LINE.match(ln)
        if mf and cur is not None and indent_of(ln) < 10 and (last is not None or fn_open is not None):
            fn_open = mf.group(1)
            notes[fn_open] = mf.group("t").strip()
            last = None
            continue
        if fn_open is not None:
            notes[fn_open] += " " + ln.strip()
            continue
        if last is not None and cur is not None:
            frag = re.sub(r"\s+\.\d+\s*$", "", ln.strip())
            frag = re.sub(r"\s{2,}.*$", "", frag).strip()
            if frag and not re.match(r"^[–-]$", frag):
                last[1] = last[1] + " " + frag
    # footnote marks glued to names
    for sct in sections:
        for row in sct["rows"]:
            mm = re.match(r"^(.*?[A-Za-z)’'])(\d{1,3})$", row[1])
            if mm:
                row[1], row[4] = mm.group(1).strip(), mm.group(2)
            else:
                mm = re.match(r"^(.*?[A-Za-z)’'])\s*(\d{1,3})\b(.*)$", row[1])
        sct["notes"] = {}
    for sct in sections:
        for row in sct["rows"]:
            if row[4] and row[4] in notes:
                sct["notes"][row[4]] = notes[row[4]]
    rows = sum(len(x["rows"]) for x in sections)
    if rows < 10:
        return None
    return sections


def upgrade_tables(blocks):
    out = []
    for b in blocks:
        if b["kind"] == "pre":
            t = parse_entity_table(b["text"])
            if t:
                for sct in t:
                    out.append({"kind": "etable", "title": sct["title"], "rows": sct["rows"], "notes": sct["notes"]})
                continue
        out.append(b)
    return out
