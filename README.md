# UAE CT Database

Public English-language database of UAE corporate tax legislation (working title).
Static website: no server, no database, no build step on the host. The finished site is the `public/` folder.

## Pilot scope

- Federal Decree-Law No. 47 of 2022 (consolidated text, with the FTA edition of 24 Oct 2025 as an archived edition)
- The amending Decree-Laws No. 60 of 2023, 40 of 2024 and 28 of 2025 (status pages; texts pending)
- Cabinet Decisions made under the Law (17 acts)
- Related acts: Federal Decree-Law No. 28 of 2022 (Tax Procedures) and Cabinet Decision No. 74 of 2023 (its Executive Regulation)

Watch list (not loaded): Cabinet Decision 209 of 2025 and the expected decision under Article 49 bis.

## Folders

| Folder | What it holds |
|---|---|
| `public/` | The generated website. This is what Cloudflare Pages publishes. Do not edit by hand. |
| `site/` | CSS, JavaScript and icon copied to `public/assets/`. |
| `tools/` | The generator: `acts_data.py` (registry of acts and editions), `textparse.py` and `model.py` (PDF text to structured articles), `build.py` (site), `qa.py` (checks). |
| `sources/pdf/` | Source PDFs exactly as downloaded from mof.gov.ae and tax.gov.ae. File name = `<act id>_<language>-<publisher>.pdf`. |
| `sources/urls.json` | Original address of every source PDF. |
| `sources/manual/` | Texts prepared by hand (machine translation of Cabinet Decision 10 of 2024, whose English text is not published). |

## Rebuild the site

Needs Python 3 and `pdftotext` (package `poppler-utils`). No other packages.

```
python3 tools/qa.py       # structural checks of the parsed texts
python3 tools/build.py    # writes ./public
```

## Add or update an act

1. Put the PDF in `sources/pdf/` and its address in `sources/urls.json`.
2. Add the act or the new edition in `tools/acts_data.py` (the previous edition stays as an archived one: `current=False`).
3. Run `qa.py`, then `build.py`, check the page, commit and push. Cloudflare Pages publishes automatically.

## Hosting

Cloudflare Pages, connected to this repository. Framework preset: None. Build command: empty. Build output directory: `public`.
