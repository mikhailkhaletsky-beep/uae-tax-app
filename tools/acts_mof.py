"""Ministerial Decisions of the Ministry of Finance on Corporate Tax (English texts only).

One row per decision: (number, year, issue date, sidebar name, topics, effective, extras).
The official titles and download addresses come from sources/md_manifest.json (collected from mof.gov.ae);
the PDF of each decision is sources/pdf/MD-<no>-<year>_EN-MOF.pdf.
Dates of issue are the Gregorian dates printed under the Minister's signature.
"""
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST = json.load(open(os.path.join(ROOT, "sources", "md_manifest.json"), encoding="utf-8"))

T_RES = "Tax residency and nexus"
T_EXE = "Exempt persons"
T_FZ = "Free zones"
T_INV = "Investment funds and partnerships"
T_PEN = "Penalties and procedures"
T_TOP = "Top-up Tax (Pillar Two)"
T_CRD = "Tax credits and incentives"
T_INC = "Taxable income and deductions"
T_REL = "Reliefs, groups and restructuring"
T_ACC = "Accounting, audit and records"

DAY_AFTER = "The day after publication"
FIFTEEN = "15 days after publication"
APPLIES_2025 = "; applies to Tax Periods starting on or after 1 January 2025"

REP_OLD = "Repealed (still applies to Tax Periods that began before 1 January 2025)"

# (no, yr, issued, name, topic, effective, extras)
ROWS = [
    (27, 2023, "2023-02-22", "Tax residency: tests for natural persons", T_RES, "1 March 2023", {}),
    (43, 2023, "2023-03-10", "Persons not required to register", T_PEN, DAY_AFTER, {}),
    (68, 2023, "2023-03-29", "Government entities treated as one Taxable Person", T_EXE, FIFTEEN, {}),
    (73, 2023, "2023-04-03", "Small Business Relief", T_REL, FIFTEEN + "; applies to Tax Periods starting on or after 1 June 2023",
     dict(history=[dict(date="2026-07-29", text="Clause (2) of Article 2 (period of the relief) replaced by Ministerial Decision No. 131 of 2026", ref="MD-131-2026")])),
    (82, 2023, "2023-04-10", "Audited financial statements (2023 rules)", T_ACC, FIFTEEN,
     dict(repealed_by="MD-84-2025", status_label=REP_OLD, note="Repealed by Article 3 of Ministerial Decision No. 84 of 2025; it continues to apply to Tax Periods that began before 1 January 2025.")),
    (83, 2023, "2023-04-10", "Temporary presence of a natural person: no Permanent Establishment", T_RES, FIFTEEN, {}),
    (97, 2023, "2023-04-27", "Transfer pricing documentation", T_ACC, DAY_AFTER, {}),
    (105, 2023, "2023-05-04", "Exempt Person status: liquidation or temporary failure", T_EXE, "The date of publication", {}),
    (114, 2023, "2023-05-09", "Accounting standards and methods", T_ACC, DAY_AFTER, {}),
    (115, 2023, "2023-05-10", "Private pension and social security funds", T_EXE, DAY_AFTER, {}),
    (116, 2023, "2023-05-10", "Participation Exemption (2023 rules)", T_REL, DAY_AFTER,
     dict(repealed_by="MD-302-2024", status_label=REP_OLD, note="Repealed by Article 15 of Ministerial Decision No. 302 of 2024; it continues to apply to Tax Periods that began before 1 January 2025.")),
    (120, 2023, "2023-05-16", "Transitional rules: opening adjustments", T_INC, DAY_AFTER, {}),
    (125, 2023, "2023-05-22", "Tax Groups (2023 rules)", T_REL, DAY_AFTER,
     dict(repealed_by="MD-301-2024", status_label=REP_OLD, note="Repealed by Article 14 of Ministerial Decision No. 301 of 2024; it continues to apply to Tax Periods that began before 1 January 2025.")),
    (126, 2023, "2023-05-23", "General interest deduction limitation", T_INC, DAY_AFTER, {}),
    (132, 2023, "2023-05-25", "Transfers within a Qualifying Group", T_REL, DAY_AFTER, {}),
    (133, 2023, "2023-05-25", "Business restructuring relief", T_REL, DAY_AFTER, {}),
    (134, 2023, "2023-05-29", "General rules for determining Taxable Income", T_INC, DAY_AFTER, {}),
    (139, 2023, "2023-06-01", "Qualifying Activities (original list)", T_FZ, "1 June 2023",
     dict(repealed_by="MD-265-2023", status_label="Repealed", note="Repealed by Article 6 of Ministerial Decision No. 265 of 2023.")),
    (247, 2023, "2023-10-16", "Tax Residency Certificates under tax treaties", T_RES, "1 March 2023", {}),
    (265, 2023, "2023-10-27", "Qualifying Activities (2023 revision)", T_FZ, "1 June 2023",
     dict(repealed_by="MD-229-2025", status_label="Repealed", note="Repealed by Article 6 of Ministerial Decision No. 229 of 2025.")),
    (261, 2024, "2024-10-28", "Unincorporated partnerships, foreign partnerships and family foundations", T_INV, "1 June 2023", {}),
    (301, 2024, "2024-12-09", "Tax Groups", T_REL, DAY_AFTER + "; applies to Tax Periods starting on or after 1 January 2025", {}),
    (302, 2024, "2024-12-10", "Participation Exemption and foreign Permanent Establishment exemption", T_REL,
     DAY_AFTER + "; applies to Tax Periods starting on or after 1 January 2025", {}),
    (84, 2025, "2025-03-25", "Audited financial statements", T_ACC, "The date of issuance" + APPLIES_2025, {}),
    (88, 2025, "2025-03-28", "Top-up Tax: OECD commentary and guidance (2025)", T_TOP, "1 January 2025",
     dict(repealed_by="MD-96-2026", status_label="Repealed", note="Repealed by Article 3 of Ministerial Decision No. 96 of 2026.",
          normalize=[(r"\bef f ective", "effective"), (r"\bf (?=rom\b|or\b)", "f"), ("ref erred", "referred"), ("Shif ting", "Shifting"),
                     ("Prof it", "Profit"), (r"Top -Up", "Top-Up")])),
    (96, 2025, "2025-04-14", "REITs: exemption conditions", T_INV, "The date of issuance" + APPLIES_2025, {}),
    (173, 2025, "2025-06-23", "Investment property at fair value: depreciation election", T_INC, "The date of issuance" + APPLIES_2025, {}),
    (229, 2025, "2025-08-28", "Free Zone Qualifying Activities and Excluded Activities", T_FZ, "1 June 2023", {}),
    (230, 2025, "2025-08-29", "Recognised Price Reporting Agencies", T_FZ, "1 June 2023", {}),
    (336, 2025, "2025-12-22", "Competent authority for Qualifying Activities", T_FZ, "1 June 2023", {}),
    (24, 2026, "2026-03-18", "R&D tax credit: implementing rules", T_CRD, "The date of issuance; applies from 1 January 2026", {}),
    (96, 2026, "2026-06-22", "Top-up Tax: OECD commentary and guidance", T_TOP, "The date of issuance; applies to Fiscal Years starting on or after 1 January 2025", {}),
    (131, 2026, "2026-07-29", "Small Business Relief: extended to 2029", T_REL, DAY_AFTER, dict(amends=["MD-73-2023"])),
    (133, 2026, "2026-08-03", "Pillar Two Information Return: filing entities", T_TOP, "The date of issuance; applies to Fiscal Years starting on or after 1 January 2025", {}),
]


def clean_title(t, no, yr):
    t = re.sub(r"^Ministerial Decision(?: No\.?)?\s*\(?\d+\)?\s*of\s*\d{4}\s*", "", t.strip(), flags=re.I)
    t = re.sub(r"\bNo\.?\s*\((\d+)\)", r"No. \1", t)
    t = re.sub(r"\bNo (\d+)\b", r"No. \1", t)
    t = t.replace("Federal Decree Law", "Federal Decree-Law").replace("Top-Up", "Top-up")
    t = re.sub(r"\s+", " ", t).strip()
    return f"Ministerial Decision No. {no} of {yr} " + t


def build():
    acts = []
    by_id = {}
    for no, yr, issued, name, topic, eff, ex in sorted(ROWS, key=lambda r: (r[2], r[0])):
        key = f"MD-{no}-{yr}"
        man = MANIFEST[key]
        a = dict(
            id=key, slug=f"md-{no}-{yr}", group="ministerial", short=f"Ministerial Decision No. {no} of {yr}",
            name=name, subject=name, title=clean_title(man["title"], no, yr), topics=[topic],
            status="repealed" if ex.get("repealed_by") else "in_force",
            status_label=ex.get("status_label", "In force"),
            issued=issued, effective=eff, en_only=True,
            editions=[dict(id="mof", label="Text as published by the Ministry of Finance", short="MOF text", date=issued,
                           src=f"{key}_EN-MOF", current=True, publisher="Ministry of Finance")],
        )
        if ex.get("normalize"):
            a["normalize"] = ex["normalize"]
        for k in ("repealed_by", "amends", "history"):
            if ex.get(k):
                a[k] = ex[k]
        if ex.get("note"):
            a["status_note"] = ex["note"]
        acts.append(a)
        by_id[key] = a
    for a in acts:                                  # "repeals" is the mirror of "repealed_by"
        if a.get("repealed_by"):
            by_id[a["repealed_by"]].setdefault("repeals", []).append(a["id"])
    return acts
