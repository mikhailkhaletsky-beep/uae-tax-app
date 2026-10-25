"""Check that every internal link and #anchor in public/ points to something that exists."""
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urldefrag, urlparse

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("link", "script", "object") and (a.get("href") or a.get("src") or a.get("data")):
            self.links.append(a.get("href") or a.get("src") or a.get("data"))
        if tag == "option" and a.get("value", "").startswith("/"):
            self.links.append(a["value"])


pages = {}
for dp, _, fs in os.walk(ROOT):
    for f in fs:
        if f.endswith(".html"):
            path = os.path.join(dp, f)
            p = P()
            p.feed(open(path, encoding="utf-8").read())
            pages[os.path.relpath(path, ROOT)] = p


def resolve(url):
    u = url.lstrip("/")
    for cand in (u, u + "index.html", os.path.join(u, "index.html")):
        if cand in pages or os.path.isfile(os.path.join(ROOT, cand)):
            return cand
    return None


bad, n = [], 0
for rel, p in pages.items():
    base = "/" + os.path.dirname(rel) + "/" if os.path.dirname(rel) else "/"
    for href in p.links:
        if href.startswith(("http://", "https://", "mailto:")):
            continue
        n += 1
        url, frag = urldefrag(href)
        if not url:
            tgt = rel
        else:
            path = urlparse(url).path
            if not path.startswith("/"):
                path = os.path.normpath(base + path)
            tgt = resolve(path.split("?")[0])
        if tgt is None:
            bad.append((rel, href, "missing page"))
        elif frag and tgt in pages and frag not in pages[tgt].ids and not frag.startswith("view="):
            bad.append((rel, href, "missing anchor"))
print(f"{len(pages)} pages, {n} internal links checked, {len(bad)} problems")
for b in bad[:40]:
    print("  ", b)
sys.exit(1 if bad else 0)
