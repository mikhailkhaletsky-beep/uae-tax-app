"""Parse FTA guides and Public Clarifications (PDF) into the block model used by model.py / build.py.

pdfplumber supplies geometry and fonts. The result is a list of blocks:
    {"kind": "heading", "lvl": 1..4, "num": "2.1.1", "title": "..."}
    {"kind": "p", "text": "...", "level": 0, "marker": "", "note": "25,26", "box": 0, "strong": bool}
    {"kind": "defs", "rows": [(term, text, note), ...]}
    {"kind": "table", "rows": [[cell, ...], ...], "hdr": 1, "note": ""}
and a dict of footnotes {"25": "text"}.

Inline emphasis inside "text" uses the private-use marks B_ON / B_OFF (bold) that build.py turns into <strong>.
Text is never dropped: whatever the parser cannot classify becomes a plain paragraph.
"""
import collections
import re
import unicodedata

import pdfplumber

B_ON, B_OFF = "", ""
ARABIC = re.compile(r"[֐-ࣿיִ-﷿ﹰ-﻿‏‎‪-‮⁦-⁩]")
MARK = re.compile(r"⟦(\d{1,3}(?:[,–-]\d{1,3})*)⟧")           # footnote marker placeholder, ⟦25⟧, ⟦2,3⟧ or ⟦4–6⟧


MARK1 = re.compile(r"⟦(\d{1,3})⟧")        # a single marker: the start of a footnote text


def note_ids(s):
    """"2,3" -> ["2","3"]; "4–6" -> ["4","5","6"]."""
    out = []
    for part in s.split(","):
        m = re.fullmatch(r"(\d{1,3})[–-](\d{1,3})", part)
        if m and 0 < int(m.group(2)) - int(m.group(1)) < 30:
            out += [str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)]
        else:
            out.append(part)
    return out
DOTS = re.compile(r"\.{5,}\s*\d{1,3}\s*$|(?:\. ){5,}\d{1,3}\s*$")
BULLETS = {"●", "•", "o", "-", "–", "—", "■", "▪", "◦", "➢", "", "", "", "", "", "", "·", "✓", "➔", "➤", "●"}
RE_NUMMARK = re.compile(r"^(?:\(?\d{1,2}[.)]|\(?[a-z][.)]|\(?(?:ix|iv|v?i{1,3}|x{1,2})[.)]|\([ivx]+\)|\(\d{1,2}\))$")
RE_LITNUM = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\.?$")


# Public Clarifications are bilingual (English left, Arabic right); the English half only, unnumbered headings
CLAR_CFG = dict(xmax=0.505, skipfont=("Arial", "Arabic"), style="clar", ftr=30)


CLAR_TOP = {"issue", "summary", "detailed analysis", "detailed analysis and application", "legislative references", "legislative reference",
            "background", "conclusion", "introduction", "scope", "effective date", "purpose", "analysis"}


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def load_outline(path):
    """PDF bookmarks (a few guides carry them) as [(level, number, normalised title)]; [] when there are none."""
    try:
        import pypdf
        r = pypdf.PdfReader(path)
        out = []

        def walk(items, lvl):
            for x in items:
                if isinstance(x, list):
                    walk(x, lvl + 1)
                else:
                    t = re.sub(r"\s+", " ", str(x.title)).strip()
                    m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", t)
                    try:
                        pg = r.get_destination_page_number(x) + 1
                    except Exception:
                        pg = 0
                    out.append((lvl, m.group(1) if m else "", norm_title(m.group(2) if m else t), m.group(2) if m else t, pg))
        walk(r.outline, 1)
        return out
    except Exception:
        return []


def is_bold(fn):
    f = fn.lower()
    return "bold" in f or "black" in f or f.endswith(",b") or "-bd" in f


def is_ital(fn):
    f = fn.lower()
    return "italic" in f or "oblique" in f


class Line:
    __slots__ = ("page", "words", "x0", "x1", "top", "bottom", "size", "bold", "text", "color", "boxed", "kind",
                 "ital", "mk_first", "rich")

    def __init__(self, page, words):
        self.page = page
        self.words = words
        self.x0 = min(w["x0"] for w in words)
        self.x1 = max(w["x1"] for w in words)
        self.top = min(w["top"] for w in words)
        self.bottom = max(w["bottom"] for w in words)
        main = [w for w in words if not w.get("marker")]
        ref = main or words
        self.size = round(max(w["size"] for w in ref), 1)
        self.bold = all(w["bold"] for w in ref)
        self.ital = all(w["ital"] for w in ref)
        self.color = tuple(round(c, 1) for c in (ref[0].get("color") or ()))
        self.boxed = 0
        self.kind = None
        self.text = self.make_text(words, inline=False)
        self.rich = self.make_text(words, inline=True)

    @staticmethod
    def make_text(words, inline=True):
        """Join the words of a line; markers stick to the word before them; bold runs get B_ON / B_OFF."""
        out, bold = "", False
        for w in words:
            t = w["text"]
            if w.get("marker"):
                out += "\u27e6" + t + "\u27e7"
                continue
            sep = " " if out and not out.endswith("\u27e7") else ""
            if out.endswith("\u27e7"):
                sep = " "
            if inline:
                if w["bold"] and not bold:
                    out += sep + B_ON + t
                    bold = True
                    continue
                if not w["bold"] and bold:
                    out += B_OFF
                    bold = False
            out += sep + t
        if inline and bold:
            out += B_OFF
        return out


def clean(s):
    s = unicodedata.normalize("NFC", s.replace(" ", " ").replace("​", "").replace("", "•").replace("", "▪"))
    return re.sub(r"[ \t]+", " ", s).strip()


def page_words(page, cfg):
    W = page.width
    ws = page.extract_words(extra_attrs=["fontname", "size", "non_stroking_color"], x_tolerance=1.5, y_tolerance=2,
                            keep_blank_chars=False, use_text_flow=False)
    out = []
    xmax = cfg.get("xmax")
    for w in ws:
        if xmax and w["x0"] > W * xmax:
            continue
        if ARABIC.search(w["text"]):
            continue
        if cfg.get("skipfont") and any(f in w["fontname"] for f in cfg["skipfont"]):
            continue
        w["bold"] = is_bold(w["fontname"])
        w["ital"] = is_ital(w["fontname"])
        w["color"] = w.get("non_stroking_color")
        out.append(w)
    return out


def cluster_lines(words, body):
    """Group words by baseline; raised small numbers become footnote markers of the line they sit on."""
    main = [w for w in words if not (re.fullmatch(r"\d{1,3}(?:[,–-]\d{1,3})*", w["text"]) and w["size"] <= body * 0.8)]
    small = [w for w in words if w not in main]
    rows = []
    for w in sorted(main, key=lambda w: (w["bottom"], w["x0"])):
        if rows and abs(rows[-1][0] - w["bottom"]) <= 2.2:
            rows[-1][1].append(w)
        else:
            rows.append([w["bottom"], [w]])
    lines = []
    for _, ws in rows:
        ws.sort(key=lambda w: w["x0"])
        lines.append(ws)
    orphan = []
    for s in small:
        host = None
        for ws in lines:
            top = min(w["top"] for w in ws)
            bot = max(w["bottom"] for w in ws)
            sz = max(w["size"] for w in ws)
            if top - 4 <= s["top"] and s["bottom"] <= bot + 3 and sz >= s["size"] * 1.2 and \
                    (s["x0"] >= min(w["x0"] for w in ws) - 22) and s["x0"] <= max(w["x1"] for w in ws) + 12:
                host = ws
                break
        if host is None:
            orphan.append(s)
            continue
        s = dict(s, marker=True)
        host.append(s)
        host.sort(key=lambda w: w["x0"])
    for s in orphan:                       # small numbers that sit on no line: ordinary words (table cells, axis labels ...)
        lines.append([s])
    lines.sort(key=lambda ws: (min(w["top"] for w in ws)))
    return lines


class Doc:
    def __init__(self, path, cfg=None):
        self.path = path
        self.cfg = cfg or {}
        self.pages = []                 # per page: dict(lines=[Line], H=, W=, tables=[], boxes=[])
        self.body = 12.0
        self.margin = 72.0
        self.pitch = 14.0
        self.right = 540.0
        self.loose = False

    # ------------------------------------------------------------------ pass 1
    def load(self):
        pdf = pdfplumber.open(self.path)
        raw = []
        sizes = collections.Counter()
        for pi, page in enumerate(pdf.pages):
            ws = page_words(page, self.cfg)
            for w in ws:
                sizes[round(w["size"])] += len(w["text"])
            raw.append((page, ws))
        tot = sum(sizes.values()) or 1
        big = [sz for sz, n in sizes.items() if n / tot >= 0.25]
        self.body = float(max(big)) if big else (float(sizes.most_common(1)[0][0]) if sizes else 12.0)
        for pi, (page, ws) in enumerate(raw):
            boxes = self.find_boxes(page)
            if self.cfg.get("qbox"):
                qbox_numbers(ws, boxes)
            lines = [Line(pi + 1, wl) for wl in cluster_lines(ws, self.body)]
            info = dict(lines=lines, H=page.height, W=page.width, tables=[], boxes=[])
            info["boxes"] = boxes
            info["tables"] = self.find_tables(page, info["boxes"])
            self.pages.append(info)
        pdf.close()
        xs = collections.Counter(round(l.x0) for p in self.pages for l in p["lines"] if abs(l.size - self.body) < 0.6 and len(l.text) > 40)
        self.margin = float(xs.most_common(1)[0][0]) if xs else 72.0
        dys = collections.Counter()
        rights = []
        for p in self.pages:
            L = [l for l in p["lines"] if abs(l.size - self.body) < 0.6]
            for a, b in zip(L, L[1:]):
                if 0 < b.top - a.top < 40:
                    dys[round(b.top - a.top)] += 1
            rights += [l.x1 for l in L if len(l.text) > 50]
        self.pitch = float(dys.most_common(1)[0][0]) if dys else 14.0
        rights.sort()
        self.right = rights[int(len(rights) * 0.9)] if rights else 540.0
        self.loose = self.pitch > 1.5 * self.body

    def find_boxes(self, page):
        out = []
        W = page.width
        for r in page.rects:
            col = r.get("non_stroking_color")
            if not r.get("fill") or col is None:
                continue
            c = col if isinstance(col, (int, float)) else (col[0] if len(col) == 1 else None)
            if len(col) == 3 if hasattr(col, "__len__") else False:
                if max(col) - min(col) < 0.03:
                    c = col[0]
            if c is None or not (0.75 <= c <= 0.93):
                continue
            w, h = r["x1"] - r["x0"], r["bottom"] - r["top"]
            if w >= W * 0.55 and h >= 28 and h < page.height * 0.95:
                out.append((r["x0"], r["top"], r["x1"], r["bottom"]))
        # keep outermost only
        out = [b for b in out if not any(o is not b and o[0] <= b[0] + 1 and o[1] <= b[1] + 1 and o[2] >= b[2] - 1 and o[3] >= b[3] - 1 and o != b for o in out)]
        return sorted(set(out), key=lambda b: b[1])

    def find_tables(self, page, boxes):
        res = []
        try:
            tabs = page.find_tables()
        except Exception:
            return res
        for t in tabs:
            x0, top, x1, bot = t.bbox
            if any(abs(x0 - b[0]) < 8 and abs(top - b[1]) < 8 and abs(x1 - b[2]) < 8 and abs(bot - b[3]) < 8 for b in boxes):
                continue
            rows = t.extract()
            nrows, ncols = len(rows), max((len(r) for r in rows), default=0)
            filled = sum(1 for r in rows for c in r if c and c.strip())
            if nrows < 2 or ncols < 2 or filled < 0.45 * nrows * ncols:
                continue
            if (x1 - x0) < 120 or (bot - top) < 30:
                continue
            res.append(dict(bbox=(x0, top, x1, bot), rows=rows))
        return res


# ---------------------------------------------------------------------------------------------- pass 2
def norm_rep(t):
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", t.strip().lower()))


def qbox_numbers(words, boxes):
    """Tax Return guide: every question sits in a grey box with its number in a left cell, centred between the lines.
    The number is moved onto the first line of the question so that the box reads "5.4.1 Did the Taxable Person ...?"."""
    for b in boxes:
        band = [w for w in words if b[1] - 2 <= (w["top"] + w["bottom"]) / 2 <= b[3] + 2]
        nums = [w for w in band if re.match(r"^\d{1,2}(?:\.\d{1,2})+\.?$", w["text"]) and w["x1"] <= b[0] + 0.2 * (b[2] - b[0])]
        rest = [w for w in band if w not in nums and w["x0"] >= b[0] - 3]
        if not nums or not rest:
            continue
        first = min(rest, key=lambda w: w["top"])
        for n in nums:
            n["top"], n["bottom"] = first["top"], first["bottom"]


def in_box(l, boxes, left=3):
    cy = (l.top + l.bottom) / 2
    for i, b in enumerate(boxes):
        if b[1] - 2 <= cy <= b[3] + 2 and l.x0 >= b[0] - left and l.x1 <= b[2] + 6:
            return i + 1
    return 0


def in_table(l, tables):
    cy = (l.top + l.bottom) / 2
    x = (l.x0 + l.x1) / 2
    for i, t in enumerate(tables):
        b = t["bbox"]
        if b[1] - 1 <= cy <= b[3] + 1 and b[0] - 3 <= x <= b[2] + 3:
            return i + 1
    return 0


class Builder:
    def __init__(self, doc):
        self.d = doc
        self.cfg = doc.cfg
        self.notes = {}
        self.page_notes = {}
        self.uid = {}
        self.blocks = []
        self.cover = []
        self.toc_pages = set()
        self.endnotes = {}
        self.auto2 = True
        self.outline = load_outline(doc.path) if doc.cfg.get("style") != "clar" else []
        self.optr = 0

    # -- classification helpers
    def strip_noise(self):
        d = self.d
        npages = len(d.pages)
        rep = collections.Counter()
        for p in d.pages:
            seen = set()
            for l in p["lines"]:
                if l.top > p["H"] * 0.85 or l.top < p["H"] * 0.12:
                    seen.add(norm_rep(l.text))
            rep.update(seen)
        repeated = {k for k, c in rep.items() if c >= max(3, 0.3 * npages) and k}
        for pi, p in enumerate(d.pages):
            keep = []
            for l in p["lines"]:
                if l.top < self.cfg.get("hdr", 62) or l.top > p["H"] - self.cfg.get("ftr", 72):
                    continue
                if norm_rep(l.text) in repeated and (l.top > p["H"] * 0.85 or l.top < p["H"] * 0.12):
                    continue
                keep.append(l)
            p["lines"] = keep

    def find_toc(self):
        d = self.d
        if self.cfg.get("style") == "clar":
            first = d.pages[0]["lines"]
            k = next((i for i, l in enumerate(first) if l.bold and l.text.strip().lower() in ("issue", "summary", "background")), 0)
            self.cover = first[:k]
            d.pages[0]["lines"] = first[k:]
            self.first = 0
            return
        for pi, p in enumerate(d.pages):
            n = sum(1 for l in p["lines"] if DOTS.search(l.text))
            if n >= 3:
                self.toc_pages.add(pi)
        first_after = (max(self.toc_pages) + 1) if self.toc_pages else 0
        if not self.toc_pages and self.cfg.get("cover", True) and len(d.pages) > 3 and self.cfg.get("has_cover", False):
            first_after = 1
        self.first = first_after
        # cover = everything before the first TOC page
        lo = min(self.toc_pages) if self.toc_pages else 0
        for pi in range(lo):
            self.cover += d.pages[pi]["lines"]

    def split_footnotes(self, p):
        """Remove the footnote zone from the page's lines and record the notes."""
        lines = p["lines"]
        body = self.d.body
        zone = []
        i = len(lines)
        while i > 0:
            l = lines[i - 1]
            if l.size <= body - 1.4 and l.top > p["H"] * 0.5 and not l.boxed and not l.kind == "table":
                zone.insert(0, l)
                i -= 1
            else:
                break
        if not zone:
            return
        start = next((k for k, l in enumerate(zone) if MARK1.match(l.text)), None)
        if start is None:
            return
        zone = zone[start:]
        cut = len(lines) - len(zone)
        p["lines"] = lines[:cut]
        cur = None
        pn = self.page_notes.setdefault(zone[0].page, {})
        for l in zone:
            m = MARK1.match(l.text)
            if m:
                cur = m.group(1)
                pn[cur] = clean(l.text[m.end():])
            elif cur:
                pn[cur] += " " + clean(l.text)

    def collect_endnotes(self):
        """Public Clarifications keep their footnotes after the "Legislative References" list, numbered through the document."""
        self.endnotes = {}
        if self.cfg.get("style") != "clar":
            return
        state, cur = 0, None
        for p in self.d.pages:
            keep = []
            for l in p["lines"]:
                if state == 0:
                    if l.bold and l.text.strip().lower().startswith("legislative"):
                        state = 1
                    keep.append(l)
                    continue
                m = MARK1.match(l.text)
                if not m:                       # a bare number starts a note only if it is a new one (a wrapped line may begin with "4 of ...")
                    m = re.match(r"^(\d{1,2})\s+(?=\S)", l.text)
                    if m and m.group(1) in self.endnotes:
                        m = None
                if m and (state == 2 or (l.size < self.d.body and int(m.group(1)) == 1)):
                    cur = m.group(1)
                    self.endnotes[cur] = clean(l.text[m.end():])
                    state = 2
                    continue
                if state == 2 and cur:
                    self.endnotes[cur] += " " + clean(l.text)
                    continue
                keep.append(l)
            p["lines"] = keep

    def sync_outline(self, title):
        """A heading found by its number moves the bookmark pointer past the matching entry."""
        t = norm_title(title)
        for k in range(self.optr, min(self.optr + 4, len(self.outline))):
            if self.outline[k][2] == t:
                self.optr = k + 1
                return

    def heading_info(self, l):
        """(level, literal-number-or-None, title-start-x) when the line is a heading, else None."""
        d = self.d
        txt = re.sub(r"⟦\d+⟧", "", l.text).strip()
        if self.cfg.get("style") == "clar":
            # Public Clarifications: unnumbered headings, bold = level 1, bold italic or italic = level 2
            if l.boxed or not txt or len(txt) > 150:
                return None
            if l.bold:
                if l.size < d.body - 0.6 and not txt.startswith("Legislative"):
                    return None
                top = txt.rstrip(":").strip().lower() in CLAR_TOP
                return (1 if (top and not l.ital) else 2, None, l.x0)
            if l.ital and l.size >= d.body - 0.6 and not txt.endswith((".", ";", ":", ",")) and abs(l.x0 - d.margin) < 4:
                return (2, None, l.x0)
            return None
        if not l.bold or l.boxed:
            return None
        if not txt or len(txt) > 230:
            return None
        if self.outline:
            lt = norm_title(txt)
            for k in range(self.optr, min(self.optr + 4, len(self.outline))):
                lvl, num, nt, otitle, opg = self.outline[k]
                if lt and len(lt) >= 4 and (nt == lt or (nt.startswith(lt) and len(lt) >= 12)) and l.x0 - d.margin < 90 \
                        and (not opg or abs(l.page - opg) <= 1):
                    ws = [w for w in l.words if not w.get("marker")]
                    if not RE_LITNUM.match(ws[0]["text"]) or len(ws) < 2:
                        self.optr = k + 1
                        return (lvl, None, l.x0, num, otitle, max(0, len(nt) - len(lt)))
                    break
        ws = [w for w in l.words if not w.get("marker")]
        first = ws[0]["text"]
        lit = None
        mm = RE_LITNUM.match(first)
        if mm and len(ws) > 1 and "." in first.rstrip(".") + "." and l.size >= d.body - 0.6:
            lit = mm.group(1)
        # a real heading is one run of text; a gap inside means table-like cells
        gaps = [ws[i + 1]["x0"] - ws[i]["x1"] for i in range(len(ws) - 1)]
        gaps_main = gaps[1:] if lit else gaps
        if gaps_main and max(gaps_main) > 2.2 * l.size:
            return None
        indent = l.x0 - d.margin
        if l.size >= d.body + 3:
            return (1, lit, ws[1]["x0"] if lit else l.x0)
        if lit:
            return (len(lit.split(".")), lit, ws[1]["x0"])
        if self.auto2 and indent >= 25 and l.size >= d.body - 0.6 and not txt.endswith(":") and indent < 60:
            return (2, None, l.x0)
        return None

    def build(self):
        d = self.d
        self.strip_noise()
        self.find_toc()
        self.collect_endnotes()
        lit2 = sum(1 for p in d.pages for l in p["lines"]
                   if l.bold and re.match(r"^\d{1,2}\.\d{1,2}\.?\s+\S", l.text) and l.size >= d.body - 0.6)
        self.auto2 = lit2 < 3                 # unnumbered second-level headings are guessed only when the guide numbers few of them
        items = []              # (page, kind, obj)
        for pi, p in enumerate(d.pages):
            if pi in self.toc_pages or pi < self.first:
                continue
            for l in p["lines"]:
                l.boxed = in_box(l, p["boxes"], 50 if self.cfg.get("qbox") else 3)
                if in_table(l, p["tables"]):
                    l.kind = "table"
            self.split_footnotes(p)
            for l in p["lines"]:
                if l.kind == "table":
                    continue
                items.append((pi, l.top, "line", l))
            for t in p["tables"]:
                items.append((pi, t["bbox"][1], "table", t))
        items.sort(key=lambda it: (it[0], it[1]))
        self.assemble(items)
        for n, t in self.endnotes.items():           # notes the text never points to are kept too
            self.notes.setdefault(n, t)
        return self.blocks

    def mm(self, l):
        """Line text with its footnote markers renumbered to document-wide unique numbers."""
        pn = self.page_notes.get(l.page, {})
        if self.endnotes:
            def rep_en(m):
                out = [n for n in note_ids(m.group(1)) if n in self.endnotes]
                for n in out:
                    self.notes[n] = self.endnotes[n]
                return "\u27e6" + ",".join(out) + "\u27e7" if out else ""
            return MARK.sub(rep_en, l.rich)

        def rep(m):
            out = []
            for n in note_ids(m.group(1)):
                if n not in pn:
                    continue
                key = (l.page, n)
                if key not in self.uid:
                    self.uid[key] = len(self.uid) + 1
                    self.notes[str(self.uid[key])] = pn[n]
                out.append(str(self.uid[key]))
            return "\u27e6" + ",".join(out) + "\u27e7" if out else ""
        return MARK.sub(rep, l.rich)

    # -- paragraph assembly
    def marker_of(self, l):
        ws = [w for w in l.words if not w.get("marker")]
        if len(ws) < 2:
            return None
        w0 = ws[0]["text"]
        if w0 in BULLETS or (RE_NUMMARK.match(w0) and not re.match(r"^\d{4}\.?$", w0)):
            if w0 in ("o", "a") and len(w0) == 1 and w0 != "o":
                return None
            return w0
        return None

    def assemble(self, items):
        d = self.d
        cur = None                 # current paragraph state
        heading_state = None
        counters = [0, 0, 0, 0, 0]
        box_id = 0
        last_box_page = None
        prev_line = None
        out = self.blocks

        def flush():
            nonlocal cur
            if not cur:
                return
            text = clean(" ".join(cur["parts"]))
            text = re.sub(r"(\S)- (?=[a-z])", r"\1-", text) if False else text
            notes = []
            for m in MARK.finditer(text):
                notes += note_ids(m.group(1))
            text = MARK.sub("", text)
            text = re.sub(r"\s+([,.;:)])", r"\1", text) if False else text
            text = clean(text)
            if text.replace(B_ON, "").replace(B_OFF, "").strip():
                b = dict(kind="p", text=text, level=cur["level"], marker=cur["marker"])
                if notes:
                    b["note"] = ",".join(dict.fromkeys(notes))
                if cur["box"]:
                    b["box"] = cur["box"]
                if cur["strong"]:
                    b["strong"] = True
                b["page"] = cur["page"]
                out.append(b)
            cur = None

        def new_par(l, marker=None, level=0):
            nonlocal cur
            flush()
            cur = dict(parts=[], marker=marker or "", level=level, box=box_id if l.boxed else 0,
                       strong=l.bold and len(l.text) < 160, page=l.page, x0=l.x0, tx=None, last=l, size=l.size)

        def marker_level(x0):
            r = x0 - d.margin
            return 0 if r < 36 else (1 if r < 64 else 2)

        for pi, top, kind, obj in items:
            if kind == "table":
                flush()
                prev_line = None
                rows = [[clean((c or "").replace("\n", " ")) for c in r] for r in obj["rows"]]
                if out and out[-1]["kind"] == "table" and out[-1]["page"] == pi and False:
                    pass
                if out and out[-1]["kind"] == "table" and out[-1]["page"] == pi - 1 and len(out[-1]["rows"][0]) == len(rows[0]) \
                        and top < 150:
                    if rows and out[-1]["rows"][0] == rows[0]:
                        rows = rows[1:]
                    out[-1]["rows"] += rows
                    out[-1]["page"] = pi
                else:
                    out.append(dict(kind="table", rows=rows, hdr=1, page=pi))
                continue
            l = obj
            # box bookkeeping: a new group starts when the box changes or an "Example N" title opens one
            if l.boxed:
                if (last_box_page is None) or (l.page - last_box_page > 1) or (not cur and not (out and out[-1].get("box") and out[-1].get("page") == l.page - 1)):
                    if not (out and out[-1].get("box") and out[-1].get("page") == l.page - 1 and l.page != last_box_page):
                        box_id += 1
                if re.match(r"^(Example|Case study|Illustration|Scenario)\b", l.text, re.I) and l.bold:
                    box_id += 1
                last_box_page = l.page
            if heading_state and heading_state.get("rem", 0) > 0 and l.bold and not l.boxed:
                heading_state["rem"] -= len(norm_title(re.sub(r"⟦\d+⟧", "", l.text)))
                heading_state["last"] = l
                continue
            hi = self.heading_info(l)
            if hi and len(hi) == 3 and hi[1] is None and l.size < d.body + 3 and cur is not None and cur["last"].page == l.page \
                    and cur["last"].bold and l.bold and 0 <= l.top - cur["last"].bottom < 0.9 * l.size and self.cfg.get("style") != "clar":
                hi = None
            if hi and not l.boxed:
                lvl, lit, tx = hi[:3]
                forced = hi[3] if len(hi) > 3 else None
                otitle = hi[4] if len(hi) > 4 else None
                # continuation of the previous heading line
                if heading_state and heading_state["page"] == l.page and l.top - heading_state["last"].bottom < 0.9 * l.size \
                        and (l.bold or l.ital) and l.size == heading_state["last"].size and not lit \
                        and l.x0 >= (d.margin if forced is None else min(heading_state["tx"], d.margin + 12)) - 4 \
                        and (heading_state["hl"] == lvl or forced is None):
                    heading_state["title"] += " " + clean(re.sub(r"⟦\d+⟧", "", l.text))
                    heading_state["last"] = l
                    out[heading_state["idx"]]["title"] = heading_state["title"]
                    continue
                flush()
                prev_line = None
                title = clean(re.sub(r"⟦\d+⟧", "", l.text))
                if otitle:
                    title = clean(otitle)
                if self.cfg.get("style") == "clar":
                    title = title.rstrip(":").strip()
                if forced is not None and forced:
                    comps = [int(x) for x in forced.split(".")]
                    lvl = len(comps)
                    for i, v in enumerate(comps):
                        counters[i] = v
                    for i in range(len(comps), 5):
                        counters[i] = 0
                elif lit:
                    title = clean(title[len(l.words[0]["text"]):])
                    comps = [int(x) for x in lit.split(".")]
                    lvl = len(comps)
                    for i, v in enumerate(comps):
                        counters[i] = v
                    for i in range(len(comps), 5):
                        counters[i] = 0
                else:
                    if lvl == 1 and re.match(r"^Appendix\s+\d+\b", title) and counters[0] > 0:
                        lvl = 2
                    counters[lvl - 1] += 1
                    for i in range(lvl, 5):
                        counters[i] = 0
                    for i in range(lvl - 1):
                        if counters[i] == 0:
                            counters[i] = 1
                num = ".".join(str(c) for c in counters[:lvl])
                out.append(dict(kind="heading", lvl=lvl, num=num, title=title, page=l.page, literal=bool(lit)))
                if self.cfg.get("style") == "clar":
                    out[-1]["nonum"] = True
                heading_state = dict(page=l.page, last=l, tx=tx, title=title, idx=len(out) - 1, hl=lvl,
                                     rem=(hi[5] if len(hi) > 5 else 0))
                if lit and not forced:
                    self.sync_outline(title)
                continue
            if heading_state and not hi and not l.boxed and self.cfg.get("style") != "clar" and heading_state["page"] == l.page \
                    and l.bold and l.size == heading_state["last"].size and 0 <= l.top - heading_state["last"].bottom < 0.9 * l.size \
                    and l.x0 >= d.margin - 4 and not heading_state["title"].rstrip().endswith((".", ":", "?")):
                # a heading wrapped onto bold lines the bookmark title (or the number scan) did not cover
                heading_state["title"] += " " + clean(re.sub(r"⟦\d+⟧", "", l.text))
                heading_state["last"] = l
                out[heading_state["idx"]]["title"] = heading_state["title"]
                continue
            heading_state = None
            mk = self.marker_of(l)
            # start of a new paragraph?
            brk = False
            if cur is None:
                brk = True
            else:
                pl = cur["last"]
                dy = l.top - pl.top if l.page == pl.page else None
                if mk:
                    brk = True
                elif bool(l.boxed) != bool(cur["box"]) or (l.boxed and cur["box"] != box_id):
                    brk = True
                elif dy is not None and not d.loose and dy > max(1.5 * max(l.size, pl.size), 1.3 * d.pitch):
                    brk = True
                elif dy is not None and d.loose and (dy > 1.3 * d.pitch or (
                        pl.x1 < d.right - 16 and re.search(r"[.:;?!”\")]\s*(?:\u27e6[\d,]+\u27e7)*$", pl.text))):
                    brk = True
                elif dy is not None and cur["marker"] and l.x0 < cur["x0"] - 2 and l.x0 <= d.margin + 2:
                    brk = True
                elif dy is not None and l.bold != pl.bold and l.bold and len(l.text) < 90 and not cur["strong"] and l.boxed:
                    brk = True
                elif dy is None:
                    # across a page break: continue only when the paragraph looks unfinished
                    prev = cur["parts"][-1] if cur["parts"] else ""
                    unfinished = not re.search(r"[.:;?!”\")]\s*(?:⟦\d+⟧)*$", prev.replace(B_OFF, "").replace(B_ON, ""))
                    if not unfinished or l.x0 > d.margin + 3 and not (cur["marker"] and l.x0 >= cur["x0"]) or bool(l.boxed) != bool(cur["box"]):
                        brk = True
            if brk:
                if mk:
                    new_par(l, marker=mk, level=marker_level(l.x0))
                    ws = [w for w in l.words if not w.get("marker")]
                    rich = self.mm(l)
                    cut = rich.find(ws[0]["text"]) + len(ws[0]["text"])
                    cur["parts"].append(rich[cut:].strip())
                else:
                    new_par(l)
                    cur["parts"].append(self.mm(l))
            else:
                cur["parts"].append(self.mm(l))
            cur["last"] = l
        flush()
