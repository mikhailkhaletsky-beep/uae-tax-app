#!/usr/bin/env python3
"""Static site generator for the UAE CT Database.

Usage:  python3 tools/build.py          -> writes ./public
"""
import difflib
import html
import json
import os
import re
import shutil
import sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acts_data as A  # noqa: E402
import model as M  # noqa: E402

ROOT = M.ROOT
OUT = os.path.join(ROOT, "public")
SITE_NAME = "UAE CT Database"
SITE_URL = "https://corp.uaetax.app"
SITEMAP = []
UPDATED = "25 October 2026"
HOME_ACT = "L-01"

esc = html.escape


def fmt_date(iso):
    if not iso or not re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
        return iso or ""
    import datetime
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


# --------------------------------------------------------------------------- model
ACTS, DOCS = M.build_all()
ORDER = [a["id"] for a in A.ACTS]
URLS = json.load(open(os.path.join(ROOT, "sources", "urls.json")))


def current_ed(a):
    return a["current_ed"]


def ed_by_id(a, eid):
    return next(e for e in a["editions"] if e["id"] == eid)


def act_url(aid, ed=None, tab=None):
    a = ACTS[aid]
    base = "/acts/" + a["slug"] + "/"
    cur = current_ed(a)
    is_cur = ed is None or cur is None or ed == cur["id"]
    if not is_cur:
        base += f"v/{ed}/"
    if tab:
        base += tab + "/"
    if aid == HOME_ACT and is_cur and tab is None:
        return "/"
    return base


def compare_url(aid, e1, e2):
    return f"/acts/{ACTS[aid]['slug']}/compare/{e1}/{e2}/"


def sorted_editions(a):
    return sorted(a["editions"], key=lambda e: e["date"])


# --------------------------------------------------------------------------- reference linking
ACT_REF_RE = re.compile(
    r"\b(?P<kind>Federal Decree-Law|Cabinet Decision)\s+No\.?\s*\(?(?P<no>\d+)\)?\s*(?:of|for)\s*(?:the\s+year\s+)?(?P<yr>\d{4})"
)
BYREF = {}
for _a in A.ACTS:
    m = re.match(r"^(Federal Decree-Law|Cabinet Decision) No\. (\d+) of (\d{4})", _a["short"])
    if m:
        BYREF[(m.group(1), int(m.group(2)), int(m.group(3)))] = _a["id"]

ART_RE = re.compile(r"\b(?P<w>Articles?)\s*\(?(?P<num>\d+(?:\.\d+)*)\)?(?P<bis>\s*\(?bis\)?)?(?P<more>(?:\s*(?:,|and|or)\s*\(\d+\))*)")
TAIL_RE = re.compile(
    r"^(?:\s*,?\s*(?:(?:and|or)\s+)?(?:Clauses?|Paragraphs?|Sub-?clauses?|Items?|Subparagraphs?)\s*\(?[0-9A-Za-z]+\)?(?:\s*\(\s*[0-9A-Za-z]+\s*\))*)*"
    r"\s*(?:of|in|under)\s+(?:the\s+)?(?:aforementioned\s+)?(?P<this>this\s+)?"
    r"(?P<who>(?:Federal Decree-Law|Cabinet Decision)\s+No\.?\s*\(?\d+\)?\s*(?:of|for)\s*\d{4}|Federal Decree-Law|Decree-Law|Executive Regulation|Decision|Regulation|Corporate Tax Law|Tax Procedures Law|Tax Law|Law)"
)

ARTS = {}  # act id -> {normalized num: (id, title)}
for (aid, eid), d in DOCS.items():
    if current_ed(ACTS[aid])["id"] == eid:
        ARTS[aid] = {}
        for s in d["sections"]:
            if s["type"] == "article":
                ARTS[aid].setdefault(s["num"].lower(), (s["id"], s["title"]))


def build_aliases(aid):
    """term -> act id from the definitions of the act, plus defaults."""
    al = {"Corporate Tax Law": "L-01", "Tax Procedures Law": "R-02"}
    a = ACTS[aid]
    if aid == "L-01":
        al["Decree-Law"] = "L-01"
    d = DOCS.get((aid, current_ed(a)["id"])) if current_ed(a) else None
    if d:
        for s in d["sections"]:
            if s["type"] != "article":
                continue
            for b in s["blocks"]:
                if b["kind"] != "defs":
                    continue
                for row in b["rows"]:
                    term, text = row[0], row[1]
                    mm = ACT_REF_RE.search(text)
                    if mm:
                        key = (mm.group("kind"), int(mm.group("no")), int(mm.group("yr")))
                        if key in BYREF and len(text) < 220:
                            al[term] = BYREF[key]
    return al


ALIASES = {aid: build_aliases(aid) for aid in ORDER}
BACK = defaultdict(lambda: defaultdict(list))   # target act -> target art id -> [(src act, src art id, src label)]
CITES = defaultdict(set)                        # src act -> {target acts}
CITED_BY = defaultdict(set)
ACTREF_USE = defaultdict(set)                   # acts mentioned by name


def kind_of(a):
    return "Federal Decree-Law" if a["short"].startswith("Federal Decree-Law") else "Cabinet Decision"


def link_text(text, aid, ctx_art=None, collect=False, page_ed=None):
    """Escape `text` and add links for article references and act mentions."""
    a = ACTS[aid]
    spans = []
    # article references
    for m in ART_RE.finditer(text):
        num = m.group("num") + (" bis" if m.group("bis") else "")
        num = num.lower()
        tail = text[m.end(): m.end() + 150]
        mt = TAIL_RE.match(tail)
        target = None
        if mt:
            if mt.group("this"):
                target = a.get("this_target", aid)      # amending acts quote text in which "this Decree-Law" is the amended law
            else:
                who = mt.group("who")
                mr = ACT_REF_RE.match(who)
                if mr:
                    target = BYREF.get((mr.group("kind"), int(mr.group("no")), int(mr.group("yr"))))
                elif who in ("Decree-Law", "Federal Decree-Law", "Law"):
                    target = ALIASES[aid].get("Decree-Law") or (aid if a["group"] == "law" else None)
                    if target is None and aid.startswith("CD"):
                        target = "L-01"
                elif who in ("Decision", "Regulation", "Executive Regulation"):
                    target = aid
                else:
                    target = ALIASES[aid].get(who)
        else:
            target = aid
        if not target or target not in ARTS:
            continue
        # the first number plus any further "(N)" numbers of a list such as "Articles (45) and (46)"
        refs = [(num, m.start(), m.end() - len(m.group("more")))]
        for mm in re.finditer(r"\((\d+)\)", m.group("more")):
            refs.append((mm.group(1), m.start("more") + mm.start(), m.start("more") + mm.end()))
        for num, rs, re_ in refs:
            while num not in ARTS[target] and "." in num:       # "Article 1.2.2" -> clause 2 of Article 1.2
                num = num.rsplit(".", 1)[0]
            if num not in ARTS[target]:
                continue
            art_id, art_title = ARTS[target][num]
            if target == aid:
                href = "#" + art_id
            else:
                href = act_url(target) + "#" + art_id
            tip = f"{ACTS[target]['short']}, Article {num}" + (f" - {art_title}" if art_title else "")
            label = text[rs:re_]
            spans.append((rs, re_, f'<a class="xref" href="{href}" title="{esc(tip)}">{esc(label)}</a>'))
            if collect and target != aid and ctx_art:
                BACK[target][art_id].append((aid, ctx_art[0], ctx_art[1]))
                CITES[aid].add(target)
                CITED_BY[target].add(aid)
    # act mentions
    for m in ACT_REF_RE.finditer(text):
        key = (m.group("kind"), int(m.group("no")), int(m.group("yr")))
        tgt = BYREF.get(key)
        if not tgt or tgt == aid:
            continue
        if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in spans):
            continue
        spans.append((m.start(), m.end(), f'<a class="actref" href="{act_url(tgt)}">{esc(m.group(0))}</a>'))
        if collect:
            ACTREF_USE[aid].add(tgt)
    spans.sort()
    out, pos = [], 0
    for s, e, h in spans:
        if s < pos:
            continue
        out.append(esc(text[pos:s]))
        out.append(h)
        pos = e
    out.append(esc(text[pos:]))
    return "".join(out)


# --------------------------------------------------------------------------- rendering of blocks
def fn_mark(n):
    if not n:
        return ""
    links = ",".join(f'<a id="fnref-{x}" href="#fn-{x}">{x}</a>' for x in str(n).split(","))
    return f'<sup class="fn">{links}</sup>'


def render_block(b, aid, ctx_art, collect, page_ed):
    k = b["kind"]
    L = lambda t: link_text(t, aid, ctx_art, collect, page_ed)
    if k == "p":
        lvl = min(b.get("level", 0), 4)
        mk = f'<span class="mk">{esc(b["marker"])}</span>' if b.get("marker") else ""
        cls = f"cl l{lvl}" + (" strong" if b.get("strong") else "") + (" has-mk" if b.get("marker") else "")
        return f'<p class="{cls}">{mk}{L(b["text"])}{fn_mark(b.get("note"))}</p>'
    if k == "defs":
        rows = []
        for r in b["rows"]:
            term, text, note = (r + ("",))[:3] if len(r) == 2 else r
            tid = "def-" + M.slug(term)
            rows.append(f'<div class="def" id="{tid}"><dt>{esc(term)}{fn_mark(note)}</dt><dd>{L(text)}</dd></div>')
        return '<dl class="defs">' + "".join(rows) + "</dl>"
    if k == "pre":
        return f'<div class="scroll"><pre class="layout">{esc(b["text"])}</pre></div>'
    if k == "etable":
        trs = []
        for no, name, to, frm, fn in b["rows"]:
            to_h = "" if to in ("–", "-") else esc(to)
            trs.append(f'<tr><td class="n">{esc(no)}</td><td>{esc(name)}{fn_mark("") if not fn else ""}'
                       f'{"<sup class=fn>" + esc(fn) + "</sup>" if fn else ""}</td><td>{esc(frm)}</td><td>{to_h or "&ndash;"}</td></tr>')
        notes = ""
        if b.get("notes"):
            notes = '<ol class="tnotes">' + "".join(f'<li value="{esc(n)}">{esc(t)}</li>' for n, t in b["notes"].items()) + "</ol>"
        return (f'<div class="scroll"><table class="etable"><caption>{esc(b["title"])} <span class="cnt">({len(b["rows"])})</span></caption>'
                f'<thead><tr><th>No.</th><th>Entity</th><th>Effective from</th><th>Effective to</th></tr></thead>'
                f'<tbody>{"".join(trs)}</tbody></table></div>{notes}')
    return ""


def render_doc(doc, aid, ed, collect=False):
    a = ACTS[aid]
    page_ed = ed["id"]
    is_cur = current_ed(a)["id"] == page_ed
    collect = collect and is_cur
    parts, toc = [], []
    has_titles = any(s["type"] == "chapter" and s["label"].startswith(("Title", "Part", "Book")) for s in doc["sections"])
    if doc["pre"]:
        pre = "".join(render_block(b, aid, None, False, page_ed) for b in doc["pre"])
        parts.append(f'<section class="preamble" id="preamble"><details><summary>Preamble and recitals</summary>{pre}</details></section>')
    for s in doc["sections"]:
        if s["type"] == "chapter":
            sub = has_titles and s["label"].startswith("Chapter")
            toc.append(("subchapter" if sub else "chapter", s["id"], f'{s["label"]} – {s["title"]}'))
            extra = "".join(render_block(b, aid, None, False, page_ed) for b in s.get("blocks", []))
            parts.append(f'<h2 class="chap" id="{s["id"]}"><span class="chap-l">{esc(s["label"])}</span> {esc(s["title"])}{fn_mark(s.get("note"))}</h2>{extra}')
            continue
        label = s.get("label") or f'Article {s["num"]}'
        ctx = (s["id"], f'{label}' + (f' – {s["title"]}' if s["title"] else ""))
        body = "".join(render_block(b, aid, ctx, collect, page_ed) for b in s["blocks"])
        amend = ""
        if s.get("note") and s["note"] in doc["notes"]:
            amend = f'<p class="amend">{link_text(doc["notes"][s["note"]], aid, None, collect, page_ed)}</p>'
        toc.append(("article", s["id"], label + (f' – {s["title"]}' if s["title"] else "")))
        back = f"<!--BACK:{aid}:{s['id']}-->" if is_cur else ""
        title = f'<span class="art-t">{esc(s["title"])}</span>' if s["title"] else ""
        parts.append(
            f'<section class="art" id="{s["id"]}"><h3 class="art-h"><a class="anchor" href="#{s["id"]}" aria-label="Link to {esc(label)}">#</a>'
            f'<span class="art-n">{esc(label)}</span> {title}{fn_mark(s.get("note"))}</h3>{amend}{back}{body}</section>'
        )
    notes = ""
    if doc["notes"] or doc["leftover"]:
        allnotes = dict(doc["notes"])
        allnotes.update(doc["leftover"])
        items = "".join(
            f'<li id="fn-{n}" value="{n}">{link_text(t, aid, None, collect, page_ed)} <a class="back" href="#fnref-{n}" aria-label="Back to text">&#8617;</a></li>'
            for n, t in sorted(allnotes.items(), key=lambda kv: int(kv[0]))
        )
        notes = f'<section class="notes"><h2>Notes</h2><ol>{items}</ol></section>'
    return "\n".join(parts) + notes, toc


# first pass: render all current editions (collect backlinks / citations)
RENDER = {}
for aid in ORDER:
    a = ACTS[aid]
    for ed in a["editions"]:
        d = DOCS[(aid, ed["id"])]
        h, toc = render_doc(d, aid, ed, collect=True)
        RENDER[(aid, ed["id"])] = (h, toc)


def backrefs_html(aid, art_id):
    items = BACK.get(aid, {}).get(art_id)
    if not items:
        return ""
    seen, lis = set(), []
    for src, sid, label in items:
        if (src, sid) in seen:
            continue
        seen.add((src, sid))
        lis.append(f'<li><a href="{act_url(src)}#{sid}"><b>{esc(ACTS[src]["short"])}</b></a> – {esc(label)}</li>')
    n = len(lis)
    nacts = len({s for s, _, _ in items})
    return (f'<details class="backrefs"><summary>Referred to in {n} provision{"s" if n != 1 else ""} of {nacts} act{"s" if nacts != 1 else ""}</summary>'
            f'<ul>{"".join(lis)}</ul></details>')


def fill_backrefs(h):
    return re.sub(r"<!--BACK:([^:]+):([^>]+)-->", lambda m: backrefs_html(m.group(1), m.group(2)), h)


# --------------------------------------------------------------------------- page shell
def sidebar_html(active=None):
    out = ['<nav class="side" aria-label="Acts">']
    out.append('<div class="side-top"><a class="side-link" href="/search/">Search and filter all acts</a></div>')
    for gid, gname in A.GROUPS:
        items = [aid for aid in ORDER if ACTS[aid]["group"] == gid]
        if not items:
            continue
        out.append(f'<h4>{esc(gname)}</h4><ul>')
        for aid in items:
            a = ACTS[aid]
            cls = []
            if a["status"] == "repealed":
                cls.append("repealed")
            if a.get("pending"):
                cls.append("pending")
            if aid == active:
                cls.append("active")
            tag = ""
            if a["status"] == "repealed":
                tag = '<span class="tag tag-rep">repealed</span>'
            elif a.get("pending"):
                tag = '<span class="tag tag-pend">text pending</span>'
            out.append(
                f'<li class="{" ".join(cls)}"><a href="{act_url(aid) if not a.get("pending") else "/acts/" + a["slug"] + "/"}">'
                f'<span class="s1">{esc(a["short"].replace("Federal Decree-Law No.", "FDL").replace("Cabinet Decision No.", "CD").replace(" of ", "/"))} {tag}</span>'
                f'<span class="s2">{esc(a["subject"])}</span></a></li>'
            )
        out.append("</ul>")
    out.append('<div class="side-bot"><a href="/pending/">Texts not yet loaded</a><a href="/about/">About this database</a></div></nav>')
    return "".join(out)


SIDEBAR_CACHE = {}


def page(title, body, active=None, desc="", extra_head="", body_class="", toc=None, canonical=None):
    sid = SIDEBAR_CACHE.get(active)
    if sid is None:
        sid = SIDEBAR_CACHE[active] = sidebar_html(active)
    toc_html = ""
    if toc:
        items = []
        for kind, i, label in toc:
            items.append(f'<li class="{kind}"><a href="#{i}">{esc(label)}</a></li>')
        toc_html = f'<aside class="toc"><details open><summary>On this page</summary><ul>{"".join(items)}</ul></details></aside>'
    can = f'<link rel="canonical" href="{canonical}">' if canonical else "<!--CANON-->"
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} – {SITE_NAME}</title>
<meta name="description" content="{esc(desc or 'Full texts of UAE corporate tax legislation: Federal Decree-Law No. 47 of 2022 and Cabinet Decisions, with editions, search and cross-references.')}">
{can}
<link rel="stylesheet" href="/assets/style.css"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{extra_head}
</head><body class="{body_class}">
<header class="top">
  <button class="menu" aria-label="Menu" aria-expanded="false">&#9776;</button>
  <a class="brand" href="/"><span class="logo">&sect;</span> {SITE_NAME}</a>
  <form class="sform" action="/search/" method="get" role="search"><input type="search" name="q" placeholder="Search all texts" aria-label="Search all texts" autocomplete="off"></form>
</header>
<div class="shell">
{sid}
<main class="main" id="main">
{body}
<footer class="foot"><p>Unofficial database. English texts are unofficial translations published by the UAE Ministry of Finance and the Federal Tax Authority; the Arabic text prevails. This site is not legal advice. Last updated {UPDATED}.</p></footer>
</main>
{toc_html}
</div>
<script src="/assets/app.js" defer></script>
</body></html>"""


def write(path, content):
    if path.lstrip("/") == "404.html":
        content = content.replace("<!--CANON-->", "")
    if "<!--CANON-->" in content:
        d = os.path.dirname(path.lstrip("/"))
        url = SITE_URL + "/" + (d + "/" if d else "")
        content = content.replace("<!--CANON-->", f'<link rel="canonical" href="{url}">')
        SITEMAP.append(url)
    full = os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


# --------------------------------------------------------------------------- act pages
def status_chip(a):
    cls = "ok" if a["status"] == "in_force" else "bad"
    return f'<span class="chip {cls}">{esc(a["status_label"])}</span>'


def tabs(aid, ed_id, active):
    a = ACTS[aid]
    cur = current_ed(a)
    ed = ed_id or (cur["id"] if cur else None)
    items = []
    if cur:
        items.append(("text", "Text", act_url(aid, ed)))
        ar = ed_by_id(a, ed).get("ar") if ed else None
        items.append(("arabic", "Arabic original", act_url(aid, ed, "arabic")))
    items.append(("versions", "Versions", act_url(aid, None, "versions")))
    items.append(("related", "Related acts", act_url(aid, None, "related")))
    lis = "".join(f'<li class="{"on" if k == active else ""}"><a href="{u}">{t}</a></li>' for k, t, u in items)
    return f'<ul class="tabs">{lis}</ul>'


def meta_block(a):
    rows = [("Type", dict(A.GROUPS)[a["group"]]), ("Issued", fmt_date(a["issued"])), ("In effect", fmt_date(a["effective"]))]
    rows.append(("Topics", ", ".join(a["topics"])))
    cells = "".join(f'<div><dt>{k}</dt><dd>{esc(v)}</dd></div>' for k, v in rows if v)
    return f'<dl class="meta">{cells}</dl>'


def act_header(aid, ed_id, active_tab):
    a = ACTS[aid]
    cur = current_ed(a)
    banners = []
    if a["status"] == "repealed":
        note = esc(a.get("status_note", ""))
        link = f' See <a href="{act_url(a["repealed_by"])}">{esc(ACTS[a["repealed_by"]]["short"])}</a>.' if a.get("repealed_by") else ""
        banners.append(f'<div class="banner bad"><b>Repealed.</b> {note}{link}</div>')
    if cur and ed_id and ed_id != cur["id"]:
        ed = ed_by_id(a, ed_id)
        banners.append(
            f'<div class="banner warn"><b>Archived edition.</b> You are reading “{esc(ed["label"])}”. '
            f'<a href="{act_url(aid)}">Go to the current edition</a> · <a href="{compare_url(aid, ed_id, cur["id"])}">Compare with the current edition</a></div>')
    if cur and cur.get("machine"):
        banners.append('<div class="banner warn"><b>Machine translation.</b> No official English text was found for this act. The English below is an unofficial machine translation of the Arabic original, which prevails. Check it against the Arabic original tab.</div>')
    switch = ""
    if cur and len(a["editions"]) > 1:
        opts = "".join(
            f'<option value="{act_url(aid, e["id"], "arabic" if active_tab == "arabic" else None)}"{" selected" if e["id"] == (ed_id or cur["id"]) else ""}>{esc(e["short"])}{" (current)" if e.get("current") else ""}</option>'
            for e in reversed(sorted_editions(a)))
        switch = f'<label class="edsw">Edition <select data-edswitch>{opts}</select></label>'
    ed_line = ""
    if cur:
        ed = ed_by_id(a, ed_id or cur["id"])
        ed_line = f'<p class="edline">{esc(ed["label"])}</p>'
    return (f'<div class="act-head"><p class="crumb"><a href="/search/">All acts</a> / {esc(dict(A.GROUPS)[a["group"]])}</p>'
            f'<h1>{esc(a["short"])}</h1><p class="sub">{esc(a["title"])}</p>'
            f'<div class="chips">{status_chip(a)}{switch}</div>{ed_line}{"".join(banners)}{meta_block(a)}{tabs(aid, ed_id, active_tab)}</div>')


def render_text_page(aid, ed):
    a = ACTS[aid]
    cur = current_ed(a)
    h, toc = RENDER[(aid, ed["id"])]
    h = fill_backrefs(h) if ed["id"] == cur["id"] else h
    head = act_header(aid, ed["id"] if ed["id"] != cur["id"] else None, "text")
    intro = ""
    if aid == HOME_ACT and ed["id"] == cur["id"]:
        intro = ('<div class="hero"><p>Full texts of UAE corporate tax legislation with search, editions and cross-references. '
                 'The page below is the current consolidated text of the Corporate Tax Law. Use the contents list to jump to an article; '
                 'the box under each article shows the Cabinet Decisions that refer to it.</p></div>')
    src_url = URLS.get(ed["src"]) if not ed.get("manual") else None
    src = ""
    if src_url:
        src = f'<p class="provenance">Source: {esc(ed["publisher"])} publication, ed. “{esc(ed["short"])}”. <a href="{esc(src_url)}" rel="noopener">Original file</a>.</p>'
    elif ed.get("manual"):
        src = '<p class="provenance">Source: machine translation prepared for this database from the Arabic original.</p>'
    ed_note = f'<p class="ednote">{esc(ed["note"])}</p>' if ed.get("note") else ""
    disc = "" if ed.get("machine") else '<p class="disc">Unofficial English translation. The Arabic text prevails.</p>'
    body = f'{intro}<article class="doc">{head}{ed_note}{disc}<div class="text">{h}</div>{src}</article>'
    return page(a["short"], body, active=aid, toc=toc, desc=a["title"],
                canonical=None)


def render_pending_page(aid):
    a = ACTS[aid]
    head = act_header_pending(aid)
    body = f'<article class="doc">{head}<div class="banner warn"><b>Text not yet loaded.</b> {esc(a["pending"])}</div></article>'
    return page(a["short"], body, active=aid)


def act_header_pending(aid):
    a = ACTS[aid]
    return (f'<div class="act-head"><p class="crumb"><a href="/search/">All acts</a> / {esc(dict(A.GROUPS)[a["group"]])}</p>'
            f'<h1>{esc(a["short"])}</h1><p class="sub">{esc(a["title"])}</p><div class="chips">{status_chip(a)}</div>{meta_block(a)}'
            f'<ul class="tabs"><li class="on"><a href="/acts/{a["slug"]}/">Status</a></li></ul></div>')


def render_arabic_page(aid, ed):
    a = ACTS[aid]
    cur = current_ed(a)
    head = act_header(aid, ed["id"] if ed["id"] != cur["id"] else None, "arabic")
    key = ed.get("ar")
    if not key:
        body = f'<article class="doc">{head}<div class="banner warn"><b>Arabic original not yet loaded for this edition.</b> The Arabic text prevails over the English. It will be added when the file is located.</div></article>'
        return page(a["short"] + " (Arabic)", body, active=aid)
    fname = f"{a['slug']}-{ed['id']}-ar.pdf"
    src_url = URLS.get(key, "")
    body = (f'<article class="doc">{head}<p class="disc">The Arabic original is the authoritative text. It is shown below as published by the {esc(ed.get("ar_publisher") or ("Federal Tax Authority" if "FTA" in key else "Ministry of Finance"))}.</p>'
            f'<div class="pdfwrap"><object data="/ar/{fname}#view=FitH" type="application/pdf" aria-label="Arabic original"><p>Your browser cannot display the PDF inline. '
            f'<a href="/ar/{fname}">Open the Arabic original</a>.</p></object></div>'
            f'<p class="provenance"><a href="/ar/{fname}" target="_blank" rel="noopener">Open the Arabic original in a new tab</a>' + (f' · <a href="{esc(src_url)}" rel="noopener">Publisher file</a>' if src_url else "") + '</p></article>')
    return page(a["short"] + " (Arabic original)", body, active=aid)


def render_versions_page(aid):
    a = ACTS[aid]
    cur = current_ed(a)
    head = act_header(aid, None, "versions") if cur else act_header_pending(aid)
    eds = sorted_editions(a)
    rows = []
    for e in reversed(eds):
        st = '<span class="chip ok">Current</span>' if e.get("current") else '<span class="chip arch">Archived</span>'
        view = f'<a href="{act_url(aid, e["id"])}">Read</a>'
        ar = f' · <a href="{act_url(aid, e["id"], "arabic")}">Arabic</a>' if e.get("ar") else ""
        rows.append(f'<tr><td>{fmt_date(e["date"])}</td><td>{esc(e["label"])}{"<br><small>" + esc(e.get("note", "")) + "</small>" if e.get("note") else ""}</td><td>{st}</td><td>{view}{ar}</td></tr>')
    cmp = ""
    if len(eds) > 1:
        links = []
        for i in range(len(eds)):
            for j in range(i + 1, len(eds)):
                links.append(f'<li><a href="{compare_url(aid, eds[i]["id"], eds[j]["id"])}">{esc(eds[i]["short"])} &rarr; {esc(eds[j]["short"])}</a></li>')
        cmp = f'<h2>Compare editions</h2><p>Legal redline: deleted words are struck through, added words are underlined.</p><ul class="cmp">{"".join(links)}</ul>'
    hist = ""
    if a.get("history") or a.get("amends") or a.get("repeals") or a.get("repealed_by"):
        ev = []
        ev.append((a["issued"], f'Issued ({esc(a["short"])})', None))
        for h in a.get("history", []):
            ev.append((h["date"], esc(h["text"]), h.get("ref")))
        if a.get("repealed_by"):
            r = ACTS[a["repealed_by"]]
            ev.append((r["issued"], f'Repealed by {esc(r["short"])}', a["repealed_by"]))
        for rid in a.get("repeals", []):
            ev.append((a["issued"], f'Repeals {esc(ACTS[rid]["short"])}', rid))
        for rid in a.get("amends", []):
            ev.append((a["issued"], f'Amends {esc(ACTS[rid]["short"])}', rid))
        ev.sort(key=lambda x: x[0] or "")
        lis = []
        for d, t, ref in ev:
            link = f' &rarr; <a href="{act_url(ref) if not ACTS[ref].get("pending") else "/acts/" + ACTS[ref]["slug"] + "/"}">{esc(ACTS[ref]["short"])}</a>' if ref else ""
            lis.append(f'<li><time>{fmt_date(d)}</time> {t}{link}</li>')
        hist = f'<h2>History</h2><ul class="hist">{"".join(lis)}</ul>'
    tbl = ""
    if rows:
        tbl = f'<h2>Editions held in this database</h2><div class="scroll"><table class="grid"><thead><tr><th>Date</th><th>Edition</th><th>Status</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    else:
        tbl = '<p>No edition of the text is held yet.</p>'
    body = f'<article class="doc">{head}{tbl}{cmp}{hist}<p class="small">Earlier editions that are not yet loaded (for example the original 2022 text of the Law) will be added as they are located.</p></article>'
    return page(a["short"] + " – versions", body, active=aid)


def render_related_page(aid):
    a = ACTS[aid]
    head = act_header(aid, None, "related") if current_ed(a) else act_header_pending(aid)

    def li(rid, note=""):
        r = ACTS[rid]
        return f'<li><a href="{act_url(rid) if not r.get("pending") else "/acts/" + r["slug"] + "/"}"><b>{esc(r["short"])}</b></a> – {esc(r["subject"])}{note}</li>'

    sections = []
    if a.get("repealed_by"):
        sections.append(("Repealed by", [li(a["repealed_by"])]))
    if a.get("repeals"):
        sections.append(("Repeals", [li(x) for x in a["repeals"]]))
    if a.get("amends"):
        sections.append(("Amends", [li(x) for x in a["amends"]]))
    amended_by = [x["id"] for x in A.ACTS if aid in x.get("amends", [])]
    if amended_by:
        sections.append(("Amended by", [li(x) for x in amended_by]))
    if CITES.get(aid):
        sections.append(("Provisions of other acts cited in this act", [li(x) for x in sorted(CITES[aid])]))
    cb = sorted(CITED_BY.get(aid, set()))
    if cb:
        sections.append(("Acts that refer to provisions of this act", [li(x) for x in cb]))
    mentions = sorted(x for x in ACTREF_USE.get(aid, set()) if x not in CITES.get(aid, set()))
    if mentions:
        sections.append(("Other acts mentioned in the text", [li(x) for x in mentions]))
    if not sections:
        sections = [("Related acts", ["<li>No links found yet.</li>"])]
    body = "".join(f"<h2>{esc(t)}</h2><ul class='rel'>{''.join(items)}</ul>" for t, items in sections)
    return page(a["short"] + " – related acts", f'<article class="doc">{head}{body}</article>', active=aid)


# --------------------------------------------------------------------------- comparison (legal redline)
def tok(s):
    return re.findall(r"\s+|[^\s]+", s)


def word_diff(a, b):
    ta, tb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(esc(" ".join(ta[i1:i2])))
        else:
            if i2 > i1:
                out.append(f'<del>{esc(" ".join(ta[i1:i2]))}</del>')
            if j2 > j1:
                out.append(f'<ins>{esc(" ".join(tb[j1:j2]))}</ins>')
    return " ".join(x for x in out if x)


def sect_paras(s):
    """List of (kind, text) paragraphs for diffing."""
    out = []
    for b in s["blocks"]:
        k = b["kind"]
        if k == "p":
            out.append(("p", ((b.get("marker") or "") + " " + b["text"]).strip(), b.get("level", 0)))
        elif k == "defs":
            for r in b["rows"]:
                out.append(("def", f"{r[0]}: {r[1]}", 0))
        elif k == "etable":
            out.append(("etable", b, 0))
        elif k == "pre":
            out.append(("pre", b["text"], 0))
    return out


def para_html(kind, text, lvl, cls=""):
    if kind == "def":
        return f'<p class="cl l0 {cls}">{text}</p>'
    return f'<p class="cl l{min(lvl, 4)} {cls}">{text}</p>'


def diff_paragraphs(pa, pb):
    """Paragraph-aligned redline. pa/pb: lists of (kind, text, lvl). Returns (html, n_changed)."""
    ta = [p[1] if p[0] != "etable" else "TABLE:" + p[1]["title"] for p in pa]
    tb = [p[1] if p[0] != "etable" else "TABLE:" + p[1]["title"] for p in pb]
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    out, changed = [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for p in pb[j1:j2]:
                if p[0] == "etable":
                    continue
                out.append(para_html(p[0], esc(p[1]), p[2]))
            continue
        changed += 1
        A_, B_ = pa[i1:i2], pb[j1:j2]
        if tag == "replace" and len(A_) == len(B_):
            for x, y in zip(A_, B_):
                if x[0] == "etable" or y[0] == "etable":
                    continue
                out.append(para_html(y[0], word_diff(x[1], y[1]), y[2], "chg"))
        else:
            # try fuzzy pairing inside the replaced range
            used = set()
            for y in B_:
                if y[0] == "etable":
                    continue
                best, bi = 0.0, None
                for ii, x in enumerate(A_):
                    if ii in used or x[0] == "etable":
                        continue
                    r = difflib.SequenceMatcher(None, x[1].split(), y[1].split(), autojunk=False).ratio()
                    if r > best:
                        best, bi = r, ii
                if bi is not None and best >= 0.5:
                    used.add(bi)
                    out.append(para_html(y[0], word_diff(A_[bi][1], y[1]), y[2], "chg"))
                else:
                    out.append(para_html(y[0], f"<ins>{esc(y[1])}</ins>", y[2], "chg"))
            for ii, x in enumerate(A_):
                if ii not in used and x[0] != "etable":
                    out.append(para_html(x[0], f"<del>{esc(x[1])}</del>", x[2], "chg"))
    # entity tables
    ta_tabs = {p[1]["title"]: p[1] for p in pa if p[0] == "etable"}
    tb_tabs = {p[1]["title"]: p[1] for p in pb if p[0] == "etable"}
    for title in list(tb_tabs) + [t for t in ta_tabs if t not in tb_tabs]:
        h, n = diff_entity_table(title, ta_tabs.get(title), tb_tabs.get(title))
        if h:
            out.append(h)
            changed += n
    return "".join(out), changed


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def diff_entity_table(title, ta, tb):
    ra = {norm_name(r[1]): r for r in (ta["rows"] if ta else [])}
    rb = {norm_name(r[1]): r for r in (tb["rows"] if tb else [])}
    added = [r for k, r in rb.items() if k not in ra]
    removed = [r for k, r in ra.items() if k not in rb]
    changed = [(ra[k], rb[k]) for k in rb if k in ra and (ra[k][2], ra[k][3]) != (rb[k][2], rb[k][3])]
    if not (added or removed or changed):
        return "", 0
    trs = []
    for r in removed:
        trs.append(f'<tr class="rm"><td><del>{esc(r[1])}</del></td><td>removed</td><td><del>{esc(r[3])}</del></td><td><del>{esc(r[2])}</del></td></tr>')
    for r in added:
        trs.append(f'<tr class="ad"><td><ins>{esc(r[1])}</ins></td><td>added</td><td><ins>{esc(r[3])}</ins></td><td><ins>{esc(r[2])}</ins></td></tr>')
    for x, y in changed:
        trs.append(f'<tr class="ch"><td>{esc(y[1])}</td><td>dates changed</td><td>{word_diff(x[3], y[3])}</td><td>{word_diff(x[2], y[2])}</td></tr>')
    n = len(added) + len(removed) + len(changed)
    return (f'<div class="scroll"><table class="grid cmp-t"><caption>{esc(title)}: {len(added)} added, {len(removed)} removed, {len(changed)} with changed dates</caption>'
            f'<thead><tr><th>Entity</th><th>Change</th><th>Effective from</th><th>Effective to</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>'), n


def collect_tables(doc):
    return [b for s in doc["sections"] if s["type"] == "article" for b in s["blocks"] if b["kind"] == "etable"]


def render_compare_tables(aid, e1, e2):
    a = ACTS[aid]
    d1, d2 = DOCS[(aid, e1["id"])], DOCS[(aid, e2["id"])]
    ta = {t["title"]: t for t in collect_tables(d1)}
    tb = {t["title"]: t for t in collect_tables(d2)}
    parts, n = [], 0
    for title in list(tb) + [t for t in ta if t not in tb]:
        h, k = diff_entity_table(title, ta.get(title), tb.get(title))
        if h:
            parts.append(h)
            n += k
    head = (f'<div class="act-head"><p class="crumb"><a href="{act_url(aid, None, "versions")}">&larr; Versions of {esc(a["short"])}</a></p>'
            f'<h1>Compare editions</h1><p class="sub">{esc(a["short"])}</p>'
            f'<p class="edline"><b>From:</b> {esc(e1["label"])}<br><b>To:</b> {esc(e2["label"])}</p></div>')
    note = ('<p class="banner warn">Only the lists of entities are compared. The article text of the older edition is not reproduced '
            '(see its page for the reason).</p>')
    legend = '<p class="legend"><del>removed or old value</del> &nbsp; <ins>added or new value</ins></p>'
    body = (f'<article class="doc">{head}<p class="cmp-sum"><b>{n}</b> differences in the lists of entities.</p>{note}{legend}'
            f'{"".join(parts) or "<p>No differences found.</p>"}</article>')
    return page(f"Compare editions – {a['short']}", body, active=aid)


def render_compare(aid, e1, e2):
    if e1.get("tables_only") or e2.get("tables_only"):
        return render_compare_tables(aid, e1, e2)
    a = ACTS[aid]
    d1, d2 = DOCS[(aid, e1["id"])], DOCS[(aid, e2["id"])]
    s1 = {s["id"]: s for s in d1["sections"] if s["type"] == "article"}
    s2 = {s["id"]: s for s in d2["sections"] if s["type"] == "article"}
    order = []
    for s in d2["sections"]:
        if s["type"] == "article":
            order.append(s["id"])
    for i in s1:
        if i not in s2:
            order.append(i)
    pieces, changed_list, unchanged = [], [], []
    n_add = n_rem = n_chg = 0
    for i in order:
        x, y = s1.get(i), s2.get(i)
        if x and y:
            pa, pb = sect_paras(x), sect_paras(y)
            h, ch = diff_paragraphs(pa, pb)
            tchg = x["title"] != y["title"]
            if ch == 0 and not tchg:
                unchanged.append(y)
                continue
            n_chg += 1
            label = f"Article {y['num']}"
            title = word_diff(x["title"], y["title"]) if tchg else esc(y["title"])
            changed_list.append((i, f"{label} – {y['title']}"))
            pieces.append(f'<section class="art" id="{i}"><h3 class="art-h"><span class="art-n">{esc(label)}</span> <span class="art-t">{title}</span> <span class="chip warn">changed</span></h3>{h}</section>')
        elif y:
            n_add += 1
            changed_list.append((i, f"Article {y['num']} – {y['title']} (new)"))
            body = "".join(para_html(p[0], f"<ins>{esc(p[1])}</ins>", p[2]) for p in sect_paras(y) if p[0] != "etable")
            pieces.append(f'<section class="art" id="{i}"><h3 class="art-h"><span class="art-n">Article {esc(y["num"])}</span> <span class="art-t"><ins>{esc(y["title"])}</ins></span> <span class="chip ok">added</span></h3>{body}</section>')
        else:
            n_rem += 1
            changed_list.append((i, f"Article {x['num']} – {x['title']} (removed)"))
            body = "".join(para_html(p[0], f"<del>{esc(p[1])}</del>", p[2]) for p in sect_paras(x) if p[0] != "etable")
            pieces.append(f'<section class="art" id="{i}"><h3 class="art-h"><span class="art-n">Article {esc(x["num"])}</span> <span class="art-t"><del>{esc(x["title"])}</del></span> <span class="chip bad">removed</span></h3>{body}</section>')
    # preamble changes
    pre_h = ""
    pa = [("p", " ".join(((b.get("marker") or "") + " " + b["text"]).strip() for b in d1["pre"] if b["kind"] == "p"), 0)]
    pb = [("p", " ".join(((b.get("marker") or "") + " " + b["text"]).strip() for b in d2["pre"] if b["kind"] == "p"), 0)]
    h, ch = diff_paragraphs(pa, pb)
    if ch:
        pre_h = f'<section class="art" id="preamble"><h3 class="art-h"><span class="art-n">Preamble</span> <span class="chip warn">changed</span></h3>{h}</section>'
        changed_list.insert(0, ("preamble", "Preamble"))
    summary = (f'<p class="cmp-sum"><b>{n_chg}</b> article{"s" if n_chg != 1 else ""} changed, <b>{n_add}</b> added, <b>{n_rem}</b> removed; '
               f'<b>{len(unchanged)}</b> unchanged.</p>')
    note = ""
    if e1["publisher"] != e2["publisher"] and not (e1.get("machine") or e2.get("machine")):
        note = (f'<p class="banner warn">These two editions were published by different bodies ({esc(e1["publisher"])} and {esc(e2["publisher"])}). '
                'Some differences may be wording or layout choices in the English translation rather than changes in the law; check the Arabic original.</p>')
    legend = '<p class="legend"><del>deleted text</del> &nbsp; <ins>added text</ins></p>'
    nav = "".join(f'<li><a href="#{i}">{esc(l)}</a></li>' for i, l in changed_list)
    unch = ""
    if unchanged:
        unch = ('<details class="unch"><summary>Unchanged articles (' + str(len(unchanged)) + ")</summary><p>"
                + ", ".join(f'<a href="{act_url(aid, e2["id"])}#{s["id"]}">{esc("Article " + s["num"])}</a>' for s in unchanged) + "</p></details>")
    head = (f'<div class="act-head"><p class="crumb"><a href="{act_url(aid, None, "versions")}">&larr; Versions of {esc(a["short"])}</a></p>'
            f'<h1>Compare editions</h1><p class="sub">{esc(a["short"])}</p>'
            f'<p class="edline"><b>From:</b> {esc(e1["label"])}<br><b>To:</b> {esc(e2["label"])}</p></div>')
    body = f'<article class="doc">{head}{summary}{note}{legend}<div class="text">{pre_h}{"".join(pieces) or "<p>No differences found.</p>"}</div>{unch}</article>'
    toc = [("article", i, l) for i, l in changed_list]
    return page(f"Compare editions – {a['short']}", body, active=aid, toc=toc)


# --------------------------------------------------------------------------- search index
STOP = ["the", "of", "and", "to", "in", "a", "an", "or", "for", "by", "on", "as", "is", "be", "it", "at", "that", "this",
        "with", "from", "shall", "any", "which", "such", "are", "was", "has", "have", "been", "not", "its", "than", "may"]
STOPSET = set(STOP)


def stem(w):
    """Light stemmer. MUST stay identical to stem() in site/app.js."""
    w = w.lower()
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ing") and len(w) - 3 >= 3:
        w = w[:-3]
    elif w.endswith("ed") and len(w) - 2 >= 3:
        w = w[:-2]
    elif w.endswith(("xes", "ches", "shes", "zes")):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if w.endswith("e") and len(w) > 3:
        w = w[:-1]
    return w


def tokens(s):
    return [t for t in (stem(x) for x in re.findall(r"[a-z0-9]+", s.lower())) if t not in STOPSET]


def build_search():
    acts_meta, docs, postings = [], [], defaultdict(dict)
    aidx = {}
    for aid in ORDER:
        a = ACTS[aid]
        aidx[aid] = len(acts_meta)
        acts_meta.append(dict(id=aid, slug=a["slug"], short=a["short"], subject=a["subject"], group=a["group"],
                              status=a["status"], topics=[A.TOPICS.index(t) for t in a["topics"]], title=a["title"]))
    for aid in ORDER:
        a = ACTS[aid]
        cur = current_ed(a)
        # act-level doc
        d_i = len(docs)
        docs.append(dict(a=aidx[aid], e=cur["id"] if cur else "", i="", n="", h=a["title"], x=a["subject"] + ". " + ("; ".join(a["topics"])), c=1, u=act_url(aid) if cur else f"/acts/{a['slug']}/"))
        for t, c in Counter(tokens(a["title"] + " " + a["subject"] + " " + " ".join(a["topics"]))).items():
            postings[t][d_i] = c * 2
        for ed in a["editions"]:
            doc = DOCS[(aid, ed["id"])]
            is_cur = 1 if ed["id"] == cur["id"] else 0
            pieces = []
            if doc["pre_text"].strip():
                pieces.append(("preamble", "Preamble", "", doc["pre_text"]))
            for s in doc["sections"]:
                if s["type"] == "article":
                    label = s.get("label") or f'Article {s["num"]}'
                    txt = "\n".join(M.block_plain(b) for b in s["blocks"])
                    pieces.append((s["id"], label, s["title"], txt))
            for i, label, title, txt in pieces:
                if not txt.strip() and not title:
                    continue
                d_i = len(docs)
                u = (act_url(aid, ed["id"]) + ("#" + i if i else ""))
                docs.append(dict(a=aidx[aid], e=ed["id"], i=i, n=label, h=title, x=re.sub(r"\s+", " ", txt), c=is_cur, u=u))
                cnt = Counter(tokens(txt))
                for t, c in Counter(tokens(title + " " + label)).items():
                    cnt[t] += c * 3
                for t, c in cnt.items():
                    postings[t][d_i] = c
    terms = {t: [x for k, v in sorted(p.items()) for x in (k, v)] for t, p in postings.items()}
    return dict(acts=acts_meta, docs=docs, terms=terms, topics=A.TOPICS, groups=A.GROUPS, stop=STOP)


def render_search_page():
    topics = "".join(f'<label><input type="checkbox" name="tp" value="{i}"> {esc(t)}</label>' for i, t in enumerate(A.TOPICS))
    groups = "".join(f'<label><input type="checkbox" name="gr" value="{g}"> {esc(n)}</label>' for g, n in A.GROUPS)
    body = f"""<article class="doc searchpage">
<h1>Search and filter</h1>
<form id="sf" class="sfilters" onsubmit="return false">
  <div class="qrow"><input id="q" type="search" placeholder="Search the full texts, e.g. “qualifying free zone person” or “top-up tax”" autocomplete="off" autofocus><button type="submit">Search</button></div>
  <div class="fgrid">
    <fieldset><legend>Type</legend>{groups}</fieldset>
    <fieldset><legend>Status</legend><label><input type="checkbox" name="st" value="in_force"> In force</label><label><input type="checkbox" name="st" value="repealed"> Repealed</label></fieldset>
    <fieldset class="wide"><legend>Topic</legend>{topics}</fieldset>
    <fieldset><legend>Editions</legend><label><input type="checkbox" id="arch"> Include archived editions</label></fieldset>
  </div>
  <p class="hint">Leave the search box empty to list acts that match the filters. Put several words to find texts that contain all of them; use quotation marks for an exact phrase.</p>
</form>
<div id="status" class="small" role="status"></div>
<ol id="results" class="results"></ol>
<noscript><p>Search needs JavaScript.</p></noscript>
</article>"""
    return page("Search", body, desc="Search the full texts of UAE corporate tax legislation.")


def render_pending_list():
    rows = []
    for aid in ORDER:
        a = ACTS[aid]
        if a.get("pending"):
            rows.append(f'<li><b>{esc(a["short"])}</b> – {esc(a["pending"])}</li>')
        if current_ed(a) and not current_ed(a).get("ar") and not a.get("pending"):
            rows.append(f'<li><b>{esc(a["short"])}</b> – Arabic original not yet loaded.</li>')
        if current_ed(a) and current_ed(a).get("machine"):
            rows.append(f'<li><b>{esc(a["short"])}</b> – only a machine translation of the Arabic is available in English.</li>')
    watch = "".join(f'<li><b>{esc(w["short"])}</b> – {esc(w["note"])}</li>' for w in A.WATCH)
    body = (f'<article class="doc"><h1>Texts not yet loaded</h1><p>Gaps in the pilot collection, with the reason.</p><ul class="rel">{"".join(rows)}</ul>'
            f'<h2>Watch list (outside the pilot scope)</h2><p>Acts that are tracked in the weekly check but not loaded.</p><ul class="rel">{watch}</ul></article>')
    return page("Texts not yet loaded", body)


def render_about():
    body = f"""<article class="doc"><h1>About this database</h1>
<p>{SITE_NAME} is a working title for a personal, non-commercial reference database of UAE corporate tax legislation. It holds the full texts of acts, not links to other websites.</p>
<h2>Pilot scope</h2>
<p>Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses (consolidated text), the Cabinet Decisions made under it, and the Tax Procedures Law and its Executive Regulation. Ministerial Decisions, Federal Tax Authority decisions, guides and Public Clarifications will be added in later stages.</p>
<h2>How the texts were prepared</h2>
<ul class="rel"><li>English texts are taken from the publications of the Ministry of Finance (mof.gov.ae) and the Federal Tax Authority (tax.gov.ae). They are unofficial translations; the Arabic text prevails. The Arabic original of every act is available on its own tab.</li>
<li>Where no official English text exists, a machine translation is shown and labelled as such.</li>
<li>Issue and effective dates are taken from the text of each act, not from the dates shown in the portals' lists, which are often different.</li>
<li>Editions: the current consolidated text opens by default. Archived editions can be read and compared (legal redline) from the Versions tab.</li>
<li>Links between acts (for example from a Cabinet Decision to the article of the Law it implements) are generated automatically from the references in the text and should be checked.</li></ul>
<h2>Limits</h2>
<p>This site is not legal advice and is not affiliated with any authority. Always check the official publication before relying on a text. Tables are shown in simplified form.</p>
<p class="small">Last updated {UPDATED}.</p></article>"""
    return page("About", body)


# --------------------------------------------------------------------------- main
def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    # assets
    shutil.copytree(os.path.join(ROOT, "site"), os.path.join(OUT, "assets"))
    # Arabic PDFs
    for aid in ORDER:
        a = ACTS[aid]
        for ed in a["editions"]:
            if ed.get("ar"):
                src = os.path.join(M.PDF_DIR, ed["ar"] + ".pdf")
                if os.path.exists(src):
                    os.makedirs(os.path.join(OUT, "ar"), exist_ok=True)
                    shutil.copy(src, os.path.join(OUT, "ar", f"{a['slug']}-{ed['id']}-ar.pdf"))
                else:
                    ed["ar"] = None
    # pages
    for aid in ORDER:
        a = ACTS[aid]
        cur = current_ed(a)
        if not cur:
            write(f"/acts/{a['slug']}/index.html", render_pending_page(aid))
            write(f"/acts/{a['slug']}/versions/index.html", render_versions_page(aid))
            write(f"/acts/{a['slug']}/related/index.html", render_related_page(aid))
            continue
        for ed in a["editions"]:
            is_cur = ed["id"] == cur["id"]
            base = f"/acts/{a['slug']}/" + ("" if is_cur else f"v/{ed['id']}/")
            html_ = render_text_page(aid, ed)
            if aid == HOME_ACT and is_cur:
                write("/index.html", html_)
                write(f"/acts/{a['slug']}/index.html",
                      '<!doctype html><meta charset="utf-8"><title>Redirect</title><link rel="canonical" href="https://corp.uaetax.app/"><meta http-equiv="refresh" content="0; url=/"><a href="/">Federal Decree-Law No. 47 of 2022</a>')
            else:
                write(base + "index.html", html_)
            write(base + "arabic/index.html", render_arabic_page(aid, ed))
        write(f"/acts/{a['slug']}/versions/index.html", render_versions_page(aid))
        write(f"/acts/{a['slug']}/related/index.html", render_related_page(aid))
        eds = sorted_editions(a)
        for i in range(len(eds)):
            for j in range(i + 1, len(eds)):
                write(f"/acts/{a['slug']}/compare/{eds[i]['id']}/{eds[j]['id']}/index.html", render_compare(aid, eds[i], eds[j]))
    write("/search/index.html", render_search_page())
    write("/pending/index.html", render_pending_list())
    write("/about/index.html", render_about())
    write("/404.html", page("Page not found", '<article class="doc"><h1>Page not found</h1><p>The page does not exist. <a href="/">Go to the Corporate Tax Law</a> or <a href="/search/">search the database</a>.</p></article>'))
    idx = build_search()
    with open(os.path.join(OUT, "assets", "search-index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    with open(os.path.join(OUT, "sitemap.xml"), "w") as f:
        urls = sorted(set(SITEMAP))
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    with open(os.path.join(OUT, "_headers"), "w") as f:      # Cloudflare Pages response headers
        f.write("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
                "/assets/*\n  Cache-Control: public, max-age=3600\n/ar/*\n  Cache-Control: public, max-age=86400\n")
    n = sum(len(fs) for _, _, fs in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print(f"built {n} files, {size / 1e6:.1f} MB; index {os.path.getsize(os.path.join(OUT, 'assets', 'search-index.json')) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
