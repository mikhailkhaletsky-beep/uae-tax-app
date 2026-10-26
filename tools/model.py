"""Load editions (PDF -> text -> blocks) and build the in-memory model used by the site generator."""
import copy
import os
import re
import subprocess

import json

import textparse as T
import acts_data as A
import guideparse as GP

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PDF_DIR = os.path.join(ROOT, "sources", "pdf")
MANUAL_DIR = os.path.join(ROOT, "sources", "manual")
CACHE = os.path.join(ROOT, "build", "txt")

STOP_ID_RE = re.compile(r"[^a-z0-9]+")


def pdf_text(key, crop=None):
    os.makedirs(CACHE, exist_ok=True)
    tag = "crop" if crop else "lay"
    out = os.path.join(CACHE, f"{key}.{tag}.txt")
    pdf = os.path.join(PDF_DIR, key + ".pdf")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(pdf):
        cmd = ["pdftotext", "-layout"] + (crop.split() if crop else []) + [pdf, out]
        subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
    return out


def edition_text_path(ed):
    if ed.get("manual"):
        return os.path.join(MANUAL_DIR, ed["src"] + ".txt")
    return pdf_text(ed["src"], ed.get("crop"))


def tidy_title(t):
    return re.sub(r"(\w)- (?=[A-Z])", r"\1-", t or "")


def attach_notes(blocks, notes):
    """Attach footnote numbers (sequential through the document) to titles / defs / paragraph ends.
    A mark may carry several numbers glued together ("13,14")."""
    nxt = 1
    attached = {}
    MK = r"(\d{1,4}(?:\s*,\s*\d{1,4})*)"      # titles and terms: glued marks such as "1314" are allowed
    MKP = r"(\d{1,2}(?:\s*,\s*\d{1,2})*)"       # running text: one or two digits per mark, to avoid eating years

    def seq(digits, cur):
        """Split a run of digits ("1314") into consecutive footnote numbers starting near `cur`."""
        if not digits:
            return []
        for ln in (2, 1):
            if len(digits) >= ln:
                n = int(digits[:ln])
                if str(n) in notes and cur <= n <= cur + 3 and not (ln == 2 and digits[0] == "0"):
                    rest = seq(digits[ln:], n + 1)
                    if rest is not None:
                        return [n] + rest
        return None

    def take(markstr):
        nonlocal nxt
        cur, nums = nxt, []
        for tok in re.split(r"\s*,\s*", markstr.strip()):
            got = seq(tok, cur)
            if got is None:
                return False
            nums += got
            cur = got[-1] + 1
        for n in nums:
            attached[str(n)] = notes[str(n)]
        nxt = cur
        take.last = ",".join(str(n) for n in nums)
        return True

    for b in blocks:
        k = b["kind"]
        if k in ("chapter", "article") and b.get("title"):
            b["title"] = tidy_title(b["title"])
        if k == "chapter":
            m = re.match(r"^(.*?[A-Za-z])\s*" + MK + r"$", b["title"] or "")
            if m and take(m.group(2)):
                b["title"] = m.group(1).strip()
                b["note"] = take.last
        elif k == "article":
            if re.fullmatch(MK, (b["title"] or "").strip()) and (b["title"] or "").strip() and take(b["title"].strip()):
                b["note"] = take.last
                b["title"] = ""
                continue
            m = re.match(r"^(.*?[A-Za-z)])\s*" + MK + r"$", b["title"] or "")
            if m and take(m.group(2)):
                b["title"] = m.group(1).strip()
                b["note"] = take.last
        elif k == "defs":
            rows = []
            for term, d in b["rows"]:
                note = ""
                m = re.match(r"^(.*?[A-Za-z’')])\s*" + MK + r"$", term)
                if m and take(m.group(2)):
                    term, note = m.group(1).strip(), take.last
                rows.append((term, d, note))
            b["rows"] = rows
        elif k == "p":
            m = re.match(r"^(.*[.;:)”a-z])\s?" + MKP + r"$", b["text"])
            if m and take(m.group(2)):
                b["text"] = m.group(1)
                b["note"] = take.last
    # footnotes we could not place stay available as general notes
    leftover = {k: v for k, v in notes.items() if k not in attached}
    return attached, leftover


def structure(blocks):
    """Split blocks into preamble + sections (chapters/articles with their body blocks)."""
    pre, sections, cur = [], [], None
    for b in blocks:
        if b["kind"] == "chapter":
            sections.append({"type": "chapter", **b})
            cur = None
        elif b["kind"] == "article":
            cur = {"type": "article", **b, "blocks": []}
            sections.append(cur)
        else:
            if cur is None:
                if sections and sections[-1]["type"] == "chapter":
                    # text directly under a chapter heading but before an article
                    sections[-1].setdefault("blocks", []).append(b)
                else:
                    pre.append(b)
            else:
                cur["blocks"].append(b)
    sections = split_annex(sections)
    return pre, sections


def split_annex(sections):
    """Decisions that carry an annexure with its own "Article N - Title" parts and "Article N.M." articles:
    the numbered parts become headings, so the article numbers stay unique."""
    arts = [i for i, s in enumerate(sections) if s["type"] == "article"]
    dotted = [i for i in arts if "." in sections[i]["num"]]
    if not dotted:
        return sections
    first = dotted[0]
    prev = [i for i in arts if i < first]
    if not prev or "." in sections[prev[-1]]["num"]:
        return sections
    start = prev[-1]
    out = []
    # the decision's own last article may end with the annexure title (a paragraph that opens a new page)
    pre_art = next((j for j in reversed(arts) if j < start), None)
    annex_title = None
    if pre_art is not None:
        bl = sections[pre_art]["blocks"]
        if len(bl) > 1 and bl[-1]["kind"] == "p" and bl[-1].get("pb") and not bl[-1].get("marker"):
            annex_title = bl[-1]["text"]
            sections[pre_art] = dict(sections[pre_art], blocks=bl[:-1])
    for i, s in enumerate(sections):
        if i == start and annex_title:
            out.append({"type": "chapter", "kind": "chapter", "label": "Annexure", "title": annex_title, "id": "annexure"})
        if s["type"] == "article" and i >= start and "." not in s["num"]:
            c = {"type": "chapter", "kind": "chapter", "label": "Annex Article " + s["num"], "title": s["title"],
                 "id": "annex-" + s["num"].replace(" ", "-")}
            if s.get("blocks"):
                c["blocks"] = s["blocks"]
            out.append(c)
        else:
            out.append(s)
    return out


def plain_marks(t):
    return t.replace(GP.B_ON, "").replace(GP.B_OFF, "")


def block_plain(b):
    k = b["kind"]
    if k == "p":
        return plain_marks((b.get("marker") or "") + " " + b["text"]).strip()
    if k == "table":
        return "\n".join(" | ".join(plain_marks(c) for c in r if c) for r in b["rows"])
    if k == "fig":
        return b.get("alt", "")
    if k == "defs":
        return "\n".join(plain_marks(f"{r[0]}: {r[1]}") for r in b["rows"])
    if k == "pre":
        return b["text"]
    if k == "etable":
        return b["title"] + "\n" + "\n".join(f"{r[0]}. {r[1]} (effective {r[3]}{'' if r[2] in ('–','-') else ', until ' + r[2]})" for r in b["rows"])
    return ""


def _norm_str(text, rules):
    for pat, rep in rules:
        text = re.sub(pat, rep, text)
    return text


def normalize_blocks(blocks, rules):
    """Editorial terminology rules (see acts_data.NORMALIZE_LAW) applied to every text field of the parsed blocks."""
    for b in blocks:
        if "text" in b:
            b["text"] = _norm_str(b["text"], rules)
        if "title" in b and isinstance(b["title"], str):
            b["title"] = _norm_str(b["title"], rules)
        if b.get("kind") == "defs":
            b["rows"] = [tuple(_norm_str(c, rules) if isinstance(c, str) else c for c in r) for r in b["rows"]]
        if b.get("kind") == "etable":
            continue


PARSED_DIR = os.path.join(ROOT, "sources", "parsed")
GLOSSARY = re.compile(r"^(glossary|definitions?|abbreviations|definitions and abbreviations|terms and definitions)$", re.I)


def guide_blocks(ed):
    """Blocks of a guide / Public Clarification: parsed from the PDF once (slow) and kept in sources/parsed/<key>.json."""
    key = ed["src"]
    pdf = os.path.join(PDF_DIR, key + ".pdf")
    os.makedirs(PARSED_DIR, exist_ok=True)
    cache = os.path.join(PARSED_DIR, key + ".json")
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(pdf) and os.path.getmtime(cache) >= os.path.getmtime(GP.__file__):
        return json.load(open(cache, encoding="utf-8"))
    d = GP.Doc(pdf, ed.get("gcfg"))
    d.load()
    b = GP.Builder(d)
    blocks = b.build()
    out = dict(blocks=blocks, notes=b.notes, body=d.body, pages=len(d.pages))
    json.dump(out, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def glossary_defs(blocks):
    """Definition paragraphs ("**Term:** text") of a glossary section become one definitions list."""
    out, rows = [], []

    def flush():
        nonlocal rows
        if rows:
            out.append({"kind": "defs", "rows": rows})
            rows = []
    for b in blocks:
        if b["kind"] == "p" and not b.get("marker") and b["text"].startswith(GP.B_ON):
            j = b["text"].find(GP.B_OFF)
            term = b["text"][1:j].strip().rstrip(":").strip()
            rest = b["text"][j + 1:].lstrip().lstrip(":").strip()
            if 0 < len(term.split()) <= 14 and rest:
                rows.append((term, rest, b.get("note", "")))
                continue
        flush()
        out.append(b)
    flush()
    return out


def load_guide(act, ed):
    g = guide_blocks(ed)
    pre, sections, ids, cur = [], [], set(), None
    for b in g["blocks"]:
        if b["kind"] == "heading":
            sid = "s-" + b["num"].replace(".", "-")
            while sid in ids:
                sid += "x"
            ids.add(sid)
            cur = {"type": "article", "kind": "article", "num": b["num"], "label": "" if b.get("nonum") else b["num"],
                   "title": b["title"], "id": sid, "lvl": b["lvl"], "blocks": []}
            sections.append(cur)
        else:
            (cur["blocks"] if cur else pre).append(b)
    for s in sections:
        if GLOSSARY.match(s["title"].strip()):
            s["blocks"] = glossary_defs(s["blocks"])
    rules = act.get("normalize")
    if rules:
        normalize_blocks(pre, rules)
        for sct in sections:
            normalize_blocks([sct], rules)
            normalize_blocks(sct.get("blocks", []), rules)
    if act.get("sub") == "private":              # the footnotes are legal references: they stay under the answers they belong to
        for s in sections:
            ids = []
            for b in s["blocks"]:
                ids += [n for n in str(b.get("note", "")).split(",") if n]
            s["notes"] = {n: g["notes"][n] for n in dict.fromkeys(ids) if n in g["notes"]}
        arts = []
        for s in sections:
            plain = "\n".join(block_plain(b) for b in s["blocks"]) + "\n" + "\n".join(s["notes"].values())
            arts.append({"id": s["id"], "num": s["num"], "title": s["title"], "text": plain})
        return dict(act=act["id"], ed=ed["id"], pre=pre, sections=sections, notes={}, leftover={}, arts=arts,
                    pre_text="\n".join(block_plain(b) for b in pre))
    arts = []
    for s in sections:
        plain = "\n".join(block_plain(b) for b in s["blocks"])
        arts.append({"id": s["id"], "num": s["num"], "title": s["title"], "text": plain})
    used = set()
    for s in sections:
        for b in s["blocks"]:
            for n in str(b.get("note", "")).split(","):
                used.add(n)
            if b["kind"] == "defs":
                for r in b["rows"]:
                    used.update(str(r[2]).split(","))
    notes = {k: v for k, v in g["notes"].items() if k in used}
    leftover = {k: v for k, v in g["notes"].items() if k not in used}
    return dict(act=act["id"], ed=ed["id"], pre=pre, sections=sections, notes=notes, leftover=leftover, arts=arts,
                pre_text="\n".join(block_plain(b) for b in pre))


def load_edition(act, ed):
    if ed.get("fmt") == "guide":
        return load_guide(act, ed)
    path = edition_text_path(ed)
    blocks, notes = T.parse_file(path, want_notes=True)
    blocks = T.upgrade_tables(blocks)
    attached, leftover = attach_notes(blocks, notes)
    pre, sections = structure(blocks)
    rules = act.get("normalize")
    if rules:
        normalize_blocks(pre, rules)
        for sct in sections:
            normalize_blocks([sct], rules)
            normalize_blocks(sct.get("blocks", []), rules)
    if ed.get("tables_only"):
        tabs = [b for s in sections if s["type"] == "article" for b in s["blocks"] if b["kind"] == "etable"]
        pre = []
        attached, leftover = {}, {}
        sections = [{"type": "article", "kind": "article", "num": "Lists", "label": "Schedule", "title": "Lists of entities", "id": "lists", "blocks": tabs}]
    arts = []
    for s in sections:
        if s["type"] == "article":
            plain = "\n".join(block_plain(b) for b in s["blocks"])
            arts.append({"id": s["id"], "num": s["num"], "title": s["title"], "text": plain})
    doc = dict(
        act=act["id"], ed=ed["id"], pre=pre, sections=sections, notes=attached, leftover=leftover, arts=arts,
        pre_text="\n".join(block_plain(b) for b in pre),
    )
    return doc


def _recompute_arts(doc):
    arts = []
    for s in doc["sections"]:
        if s["type"] == "article":
            plain = "\n".join(block_plain(b) for b in s["blocks"])
            arts.append({"id": s["id"], "num": s["num"], "title": s["title"], "text": plain})
    doc["arts"] = arts


def _find(doc, num):
    return next(i for i, s in enumerate(doc["sections"]) if s["type"] == "article" and s["num"] == num)


def derive_edition(act, ed, docs):
    """Reconstruct an earlier edition by undoing one amending law on top of the next newer edition.
    Operations: replace (whole article taken from the source edition "orig2022"), remove (article), defs_remove
    (definitions of an article), clause_remove (a numbered clause and everything after it in an article)."""
    spec = ed["derive"]
    doc = copy.deepcopy(docs[(act["id"], spec["base"])])
    src = docs[(act["id"], "orig2022")]
    doc["ed"] = ed["id"]
    for op in spec["ops"]:
        kind, num = op[0], op[1]
        if kind == "replace":
            old = src["sections"][_find(src, num)]
            i = _find(doc, num)
            new = copy.deepcopy(old)
            new["id"] = doc["sections"][i]["id"]
            new.pop("note", None)
            doc["sections"][i] = new
        elif kind == "remove":
            del doc["sections"][_find(doc, num)]
        elif kind == "defs_remove":
            sec = doc["sections"][_find(doc, num)]
            gone = set(op[2])
            hit = 0
            for b in sec["blocks"]:
                if b["kind"] == "defs":
                    before = len(b["rows"])
                    b["rows"] = [r for r in b["rows"] if r[0] not in gone]
                    hit += before - len(b["rows"])
            assert hit == len(gone), (ed["id"], num, "definitions not found", gone)
        elif kind == "clause_remove":
            sec = doc["sections"][_find(doc, num)]
            k = next(i for i, b in enumerate(sec["blocks"]) if b["kind"] == "p" and b.get("marker") == op[2] and b.get("level", 0) == 0)
            sec["blocks"] = sec["blocks"][:k]
        else:
            raise ValueError(kind)
    doc["notes"], doc["leftover"] = {}, {}
    _recompute_arts(doc)
    return doc


def build_all():
    acts = {}
    docs = {}
    for a in A.ACTS:
        acts[a["id"]] = a
        a["current_ed"] = next((e for e in a["editions"] if e.get("current")), None)
        for src in a.get("sources", []):                 # source texts that are not shown as editions
            docs[(a["id"], src["id"])] = load_edition(a, src)
        for ed in a["editions"]:
            if not ed.get("derive"):
                docs[(a["id"], ed["id"])] = load_edition(a, ed)
        pending = sorted((e for e in a["editions"] if e.get("derive")), key=lambda e: e["date"], reverse=True)
        for ed in pending:                               # newest first: each edition is built from the next newer one
            docs[(a["id"], ed["id"])] = derive_edition(a, ed, docs)
    return acts, docs


def slug(s):
    return STOP_ID_RE.sub("-", s.lower()).strip("-")


if __name__ == "__main__":
    acts, docs = build_all()
    for (aid, eid), d in docs.items():
        words = sum(len(x["text"].split()) for x in d["arts"])
        print(f"{aid:6} {eid:16} articles={len(d['arts']):3} sections={len(d['sections']):3} notes={len(d['notes'])}/{len(d['notes'])+len(d['leftover'])} words={words}")
