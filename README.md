# UAE CT Database

Public English-language database of UAE corporate tax legislation (working title).
Static website: no server, no database, no build step on the host. The finished site is the `public/` folder.

## Pilot scope

- Federal Decree-Law No. 47 of 2022, in four editions (the version log of the Law lists them):
  the current consolidated text (as amended by FDL 60/2023, 40/2024 and 28/2025), copied from the UAE Legislation portal
  (`sources/manual/L-01_EN-UAELEG.txt`), and three earlier editions rebuilt from it by `tools/model.py` (`derive_edition`):
  as amended by FDL 60/2023 and 40/2024, as amended by FDL 60/2023, and the original 2022 text. Replaced articles are taken
  from the original English text of 2022 (`sources/pdf/L-01_EN-2022-MOF.pdf`); the rules are in the `derive` entries of `tools/acts_data.py`.
- The amending Decree-Laws No. 60 of 2023 (official English text), No. 40 of 2024 and No. 28 of 2025 (machine translations of the
  Arabic originals, `sources/manual/L-03_EN.txt`, `L-04_EN.txt`). They are reachable from the version log of the Law, not from the side panel (`nav=False`).
- Cabinet Decisions made under the Law (17 acts)
- Related acts: Federal Decree-Law No. 28 of 2022 (Tax Procedures) and Cabinet Decision No. 74 of 2023 (its Executive Regulation)

Watch list (not loaded): Cabinet Decision 209 of 2025 and the expected decision under Article 49 bis.

## Folders

| Folder | What it holds |
|---|---|
| `public/` | The generated website. This is what Cloudflare publishes. Do not edit by hand. |
| `site/` | CSS, JavaScript and icon copied to `public/assets/`. |
| `tools/` | The generator: `acts_data.py` (registry of acts and editions), `textparse.py` and `model.py` (PDF text to structured articles), `build.py` (site), `qa.py` (checks). |
| `sources/pdf/` | Source PDFs exactly as downloaded from mof.gov.ae, tax.gov.ae and uaelegislation.gov.ae (`L-01_EN-MOF.pdf`, the Ministry's consolidated text of 13 Jan 2026, is kept only for cross-checking and is not published). File name = `<act id>_<language>-<publisher>.pdf`. |
| `sources/urls.json` | Original address of every source PDF. |
| `sources/manual/` | Texts prepared by hand: the consolidated Law copied from the UAE Legislation portal, and machine translations (Cabinet Decision 10 of 2024, Federal Decree-Laws 40 of 2024 and 28 of 2025), whose English texts are not published. |

## Rebuild the site

Needs Python 3 and `pdftotext` (package `poppler-utils`). No other packages.

```
python3 tools/qa.py       # structural checks of the parsed texts
python3 tools/build.py    # writes ./public
```

## Add or update an act

1. Put the PDF in `sources/pdf/` and its address in `sources/urls.json`.
2. Add the act or the new edition in `tools/acts_data.py` (the previous edition stays as an archived one: `current=False`).
3. Run `qa.py`, then `build.py`, check the page, commit and push. Cloudflare publishes automatically (about one to two minutes).

## Hosting

Cloudflare Workers (static assets), project `uae-tax-app`, connected to this repository and published at https://corp.uaetax.app. `wrangler.jsonc` points the Worker at `public/` and serves `public/404.html` for unknown addresses.

## Weekly check

A scheduled task looks at the official listings once a week (Monday morning, Dubai time) and reports acts that are not yet in
`tools/acts_data.py` or `watch/seen.json`. It only flags; nothing is loaded until the new act is reviewed and added.
