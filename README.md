# UAE CT Database

Public English-language database of UAE corporate tax legislation (working title).
Static website: no server, no database, no build step on the host. The finished site is the `public/` folder.

## Scope

- Federal Decree-Law No. 47 of 2022, in four editions (the version log of the Law lists them):
  the current consolidated text (as amended by FDL 60/2023, 40/2024 and 28/2025), copied from the UAE Legislation portal
  (`sources/manual/L-01_EN-UAELEG.txt`), and three earlier editions rebuilt from it by `tools/model.py` (`derive_edition`):
  as amended by FDL 60/2023 and 40/2024, as amended by FDL 60/2023, and the original 2022 text. Replaced articles are taken
  from the original English text of 2022 (`sources/pdf/L-01_EN-2022-MOF.pdf`); the rules are in the `derive` entries of `tools/acts_data.py`.
- The amending Decree-Laws No. 60 of 2023 (official English text), No. 40 of 2024 and No. 28 of 2025 (machine translations of the
  Arabic originals, `sources/manual/L-03_EN.txt`, `L-04_EN.txt`). They are reachable from the version log of the Law, not from the side panel (`nav=False`).
- Cabinet Decisions made under the Law (17 acts).
- Ministerial Decisions of the Ministry of Finance (34 acts, English only; `tools/acts_mof.py`).
- Federal Tax Authority acts (English only; `tools/acts_fta.py`): FTA Decisions (14 loaded, No. 16 of 2023 listed as pending),
  22 guides (Corporate Tax Guides and Top-up Tax Guides) and 12 Public Clarifications (CTP001-CTP012). Guides and Public Clarifications are
  parsed from the PDF layout by `tools/guideparse.py` into headings, paragraphs, tables and footnotes; the result is cached in
  `sources/parsed/` (`python3 tools/parse_guides.py -f` makes the caches again, a few minutes).
- FTA Private Clarifications (sub-folder of FTA acts): compilations "Summary of FTA Private Clarifications" published by the FTA, one act per
  compilation, listed in `PRIVATE` in `tools/acts_fta.py` (1 loaded: issued up to May 2026; 28 topics, 85 questions and answers, 129 notes).
  Each topic is a section of the act; the Related acts widget under an article of the Law links to the topic that cites it
  (for example Article 17 -> Family Foundations).
- Related acts: Federal Decree-Law No. 28 of 2022 (Tax Procedures) and Cabinet Decision No. 74 of 2023 (its Executive Regulation).

Watch list (not loaded): Cabinet Decision 209 of 2025 and the expected decision under Article 49 bis.

## Folders

| Folder | What it holds |
|---|---|
| `public/` | The generated website. This is what Cloudflare publishes. Do not edit by hand. |
| `site/` | CSS, JavaScript and icon copied to `public/assets/`. |
| `tools/` | The generator: `acts_data.py` (registry of acts and editions; `acts_mof.py` and `acts_fta.py` add Ministerial and FTA acts), `textparse.py`, `guideparse.py` and `model.py` (PDF text to structured articles and sections), `build.py` (site), `qa.py` (checks). |
| `sources/pdf/` | Source PDFs exactly as downloaded from mof.gov.ae, tax.gov.ae and uaelegislation.gov.ae (`L-01_EN-MOF.pdf`, the Ministry's consolidated text of 13 Jan 2026, is kept only for cross-checking and is not published). File name = `<act id>_<language>-<publisher>.pdf`. |
| `sources/urls.json` | Original address of every source PDF. |
| `sources/manual/` | Texts prepared by hand: the consolidated Law copied from the UAE Legislation portal, and machine translations (Cabinet Decision 10 of 2024, Federal Decree-Laws 40 of 2024 and 28 of 2025), whose English texts are not published. |

## Rebuild the site

Needs Python 3, `pdftotext` (package `poppler-utils`) and, only to re-read guide PDFs (`tools/parse_guides.py`), `pdfplumber`.
The parsed guides are cached in `sources/parsed/`, so `build.py` itself needs no packages when the caches are fresh.

```
python3 tools/qa.py       # structural checks of the parsed texts
python3 tools/build.py    # writes ./public
```

## Add or update an act

1. Put the PDF in `sources/pdf/` and its address in `sources/urls.json`.
2. Add the act or the new edition in `tools/acts_data.py` (the previous edition stays as an archived one: `current=False`).
3. Run `qa.py`, then `build.py`, check the page, commit and push. Cloudflare publishes automatically (about one to two minutes).

## Add a new compilation of FTA Private Clarifications

The FTA publishes new compilations from time to time (the file "Summary of FTA Private Clarifications ...").

1. Put the PDF in `sources/pdf/` as `FTAP-<yyyy>-<mm>_EN-FTA.pdf` and add its original address to `sources/urls.json` under the same key (without `.pdf`).
2. Add one row to `PRIVATE` in `tools/acts_fta.py`: `(key "yyyy-mm", publication month "yyyy-mm", "Month yyyy" (clarifications issued up to), official title)`.
3. If the new file has a topic that is not yet in `PRIVATE_TOPICS`, add it there; then run `python3 tools/parse_guides.py FTAP-<yyyy>-<mm>_EN-FTA`, `qa.py`, `build.py`, check the page, commit and push.

A new compilation becomes a separate act in the sub-folder `FTA Private Clarifications`; the earlier ones stay as they are (newest first). Every legal reference
in the footnotes becomes a link, so the topics of a compilation appear automatically under the articles they cite in Related acts.

## Side panel order

Inside every sub-section of the side panel the acts are sorted by date, newest first; repealed (cancelled) acts always come last in their sub-section
(`sidebar_html` and the Related acts widget in `tools/build.py`).

## Hosting

Cloudflare Workers (static assets), project `uae-tax-app`, connected to this repository and published at https://corp.uaetax.app. `wrangler.jsonc` points the Worker at `public/` and serves `public/404.html` for unknown addresses.

## Weekly check

A scheduled task looks at the official listings once a week (Monday morning, Dubai time) and reports acts that are not yet in
`tools/acts_data.py` or `watch/seen.json`. It only flags; nothing is loaded until the new act is reviewed and added.
The check covers the Law, Cabinet and Ministerial Decisions, FTA Decisions, Guides, Public Clarifications and the compilations of
FTA Private Clarifications (a new or replaced "Summary of FTA Private Clarifications" file is reported).
