"""Acts of the Federal Tax Authority on Corporate Tax (English texts only): decisions, guides, Public Clarifications.

Sources: tax.gov.ae (the PDF of every item is sources/pdf/<key>_EN-FTA.pdf, its address is in sources/urls.json).
Dates of decisions are the dates printed under the title of each decision; dates of guides and Public Clarifications are
the publication dates shown in the file name or on the cover (month only where only the month is given).
"""
import re

T_RES = "Tax residency and nexus"
T_EXE = "Exempt persons"
T_FZ = "Free zones"
T_INV = "Investment funds and partnerships"
T_PEN = "Penalties and procedures"
T_TOP = "Top-up Tax (Pillar Two)"
T_INC = "Taxable income and deductions"
T_REL = "Reliefs, groups and restructuring"
T_ACC = "Accounting, audit and records"
T_NAT = "Natural persons"
T_CORE = "Core law"

LAW = "for the Purposes of Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses"
PUB = "The date of publication in the Official Gazette"

# --------------------------------------------------------------------------------------------- FTA Decisions
# (no, year, issued, sidebar name, topic, effective, official title, extras)
DECISIONS = [
    (5, 2023, "2023-04-07", "Change of Tax Period: conditions", T_PEN, "1 June 2023",
     "Conditions for Change in Tax Period " + LAW, {}),
    (6, 2023, "2023-04-07", "Tax Deregistration: timelines", T_PEN, "1 June 2023",
     "Tax Deregistration Timeline " + LAW, {}),
    (7, 2023, "2023-04-07", "Exemption applications (2023 rules)", T_EXE, "1 June 2023",
     "Provisions of Exemption from Corporate Tax " + LAW,
     dict(repealed_by="FTAD-15-2026", status_label="Repealed",
          note="Repealed by Article 4 of FTA Decision No. 15 of 2026 from the date that decision took effect (15 September 2026).")),
    (11, 2023, "2023-08-16", "Declaration by Exempt Persons", T_EXE, PUB,
     "Requirements of Submitting a Declaration for Exempt Persons for purposes of Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses", {}),
    (12, 2023, "2023-08-16", "Tax Group of government-owned subsidiaries", T_REL, PUB,
     "Conditions for Forming the Tax Group by Subsidiaries of a Government Entity " + LAW, {}),
    (13, 2023, "2023-08-16", "Conversion of foreign-currency amounts", T_INC, "1 June 2023",
     "Determination of Conditions for Conversion of Amounts Quantified in a Currency other than the United Arab Emirates Dirham for the Purposes of the Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses", {}),
    (3, 2024, "2024-02-22", "Registration timelines", T_PEN, "1 March 2024",
     "The Timeline specified for Registration of Taxable Persons for Corporate Tax for the purposes of Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses and its amendments", {}),
    (7, 2024, "2024-09-25", "Filing and payment deadline postponed", T_PEN, "25 September 2024",
     "Postponement of the Deadline to File a Tax Return and Settle the Corporate Tax Payable for Certain Tax Periods " + LAW + " and its amendments", {}),
    (5, 2025, "2025-05-19", "Unincorporated Partnerships: compliance", T_INV, "1 July 2025",
     "Determining the Tax Compliance Requirements for Unincorporated Partnerships, Foreign Partnerships and Family Foundations for the purposes of Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses and its amendments",
     dict(repeals=["FTAD-16-2023"])),
    (7, 2025, "2025-07-16", "Tax Group: audited special-purpose statements", T_ACC, "Tax Periods commencing on or after 1 January 2025",
     "Determination of the Requirements for Preparing and Maintaining Audited Special Purpose Financial Statements for a Tax Group for the purposes of Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses and its amendments", {}),
    (8, 2025, "2025-09-18", "Qualifying Investment Funds: timelines", T_INV, "Tax Periods commencing on or after 1 January 2025",
     "Determining the Timelines of Tax Compliance Requirements for Qualifying Investment Funds and investors in Qualifying Investment Funds for the purposes of Federal Decree-Law No. 47 of 2022 on the Taxation of Corporations and Businesses and its amendments", {}),
    (6, 2026, "2026-06-02", "Distribution in a Designated Zone: QFZP procedures", T_FZ, "Tax Periods starting on or after 1 January 2026",
     "Determining the Additional Procedures for the Compliance of Qualifying Free Zone Persons Engaged in the Activity of Distribution of Goods or Materials in or from a Designated Zone for the Purposes of the Taxation of Corporations and Businesses", {}),
    (12, 2026, "2026-07-16", "Top-up Tax: registration and deregistration", T_TOP, "Fiscal Years starting on or after 1 January 2025",
     "The requirements for Registration and Deregistration of Entities for the purposes of Cabinet Decision No. 142 of 2024 on the Imposition of Top-Up Tax on Multinational Enterprises", {}),
    (15, 2026, "2026-09-08", "Exemption applications", T_EXE, "15 September 2026",
     "Provisions of Exemption from Corporate Tax " + LAW + " and its amendments", dict(repeals=["FTAD-7-2023"])),
]

# Decision whose text could not be loaded (repealed; no copy found on the FTA site).
PENDING_DECISIONS = [
    (16, 2023, "2023", "Unincorporated Partnerships: registration (2023 rules)", T_INV,
     "Determining the Requirements for the Registration of the Unincorporated Partnership and Determining the Distributive Shares of Partners in an Unincorporated Partnership for the purposes of Federal Decree Law No. 47 of 2022 on the Taxation of Corporations and Businesses, and its amendments",
     "Repealed by Article 11 of FTA Decision No. 5 of 2025. The text of the 2023 decision is not available on the FTA website; it is added when a copy is located.",
     "FTAD-5-2025"),
]

# --------------------------------------------------------------------------------------------- Guides
# (cover code, issued, sidebar name, topic, official title, family)
GUIDES = [
    ("CTGGCT1", "2023-09-10", "General guide to Corporate Tax", T_CORE, "Corporate Tax – General Guide", "Corporate Tax Guide"),
    ("CTGSBR1", "2023-08-27", "Small Business Relief", T_REL, "Small Business Relief", "Corporate Tax Guide"),
    ("CTGTNP1", "2023-11-25", "Natural persons", T_NAT, "Taxation of Natural Persons under the Corporate Tax Law", "Corporate Tax Guide"),
    ("CTGTGR1", "2024-01-08", "Tax Groups", T_REL, "Tax Groups", "Corporate Tax Guide"),
    ("CTGPTN1", "2024-03-04", "Partnerships", T_INV, "Taxation of Partnerships", "Corporate Tax Guide"),
    ("CTGQGR1", "2024-04", "Qualifying Group Relief", T_REL, "Qualifying Group Relief", "Corporate Tax Guide"),
    ("CTGDTI1", "2024-07-31", "Determining Taxable Income", T_INC, "Determination of Taxable Income", "Corporate Tax Guide"),
    ("CTGTXR1", "2024-11-11", "Tax Returns", T_PEN, "Tax Returns", "Corporate Tax Guide"),
    ("CTGFF1", "2026-06-05", "Family Foundations", T_INV, "Taxation of Family Foundations", "Corporate Tax Guide"),
    ("CTGFZP1", "2024-05-20", "Free Zone Persons", T_FZ, "Free Zone Persons", "Corporate Tax Guide"),
    ("CTGRJP1", "2023-08-30", "Registration of Juridical Persons", T_PEN, "Registration of Juridical Persons", "Corporate Tax Guide"),
    ("CTGACS1", "2023-11-06", "Accounting Standards", T_ACC, "Accounting Standards and Interaction with Corporate Tax", "Corporate Tax Guide"),
    ("CTGEPF1", "2023-12-01", "Exempt Persons: public benefit, pension funds", T_EXE,
     "Exempt Persons: Public Benefit Entities, Pension Funds and Social Security Funds", "Corporate Tax Guide"),
    ("CTGIDL1", "2025-04", "Interest deduction limitation", T_INC, "Interest Deduction Limitation Rules", "Corporate Tax Guide"),
    ("CTGTP1", "2023-10-23", "Transfer Pricing", T_INC, "Transfer Pricing Guide", "Corporate Tax Guide"),
    ("CTGAPA1", "2025-12-30", "Advance Pricing Agreements", T_INC, "Advance Pricing Agreements", "Corporate Tax Guide"),
    ("CTGIFM1", "2024-05-06", "Investment Funds and Managers", T_INV, "Investment Funds and Investment Managers", "Corporate Tax Guide"),
    ("CTGEXI1", "2023-10-16", "Dividends and Participation Exemption", T_REL, "Exempt Income: Dividends and Participation Exemption", "Corporate Tax Guide"),
    ("CTGBRR1", "2024-04-17", "Business Restructuring Relief", T_REL, "Business Restructuring Relief", "Corporate Tax Guide"),
    ("CTGNRP1", "2023-10-08", "Non-Resident Persons", T_RES, "Non-Resident Persons", "Corporate Tax Guide"),
    ("TTGREG1", "2026-08", "Top-up Tax: scope and registration", T_TOP, "Scope and Registration", "Top-up Tax Guide"),
    ("TTGEIE1", "2026-08-25", "Top-up Tax: Excluded Entities", T_TOP, "Excluded Entities and Investment Entities", "Top-up Tax Guide"),
]

# --------------------------------------------------------------------------------------------- Private Clarifications
# The FTA publishes its answers to individual taxpayers as compilations ("Summary of FTA Private Clarifications").
# TO ADD A NEW COMPILATION:
#   1. put the PDF in sources/pdf/FTAP-<key>_EN-FTA.pdf and its web address in sources/urls.json under the key FTAP-<key>_EN-FTA;
#   2. add one row below: (key, issued, "covers clarifications issued up to", official title);
#   3. run  python3 tools/parse_guides.py FTAP-<key>_EN-FTA -f , then qa.py and build.py (see README).
# Each compilation is a separate act in the sidebar section "FTA Private Clarifications"; the Q&A are split by topic and every legal
# reference in the footnotes becomes a link, so the topic appears under the Law article (or Decision article) it cites in "Related acts".
PRIVATE = [
    ("2026-05", "2026-07", "May 2026", "Corporate Tax – Summary of FTA Private Clarifications issued up to May 2026"),
]
PRIVATE_TOPICS = [T_EXE, T_FZ, T_INV, T_INC, T_REL, T_ACC]
PRIVATE_CFG = dict(style="pc", marker_max=7.6)

# --------------------------------------------------------------------------------------------- Public Clarifications
# (no, issued, sidebar name, topic, official title)
CLARIFICATIONS = [
    (1, "2024-06-04", "Registration timelines", T_PEN, "Registration Timelines for Taxable Persons for Corporate Tax"),
    (2, "2024-07-21", "Related Parties: Government Entities", T_INC,
     "The definition of ‘Related Parties’ where there is a common ownership and/or Control through a Government Entity"),
    (3, "2024", "First Tax Period of a juridical person", T_PEN, "First Tax Period of a juridical person"),
    (4, "2024-10-09", "Filing and payment deadline postponed", T_PEN,
     "Postponement of the Deadline to File a Tax Return and Settle the Corporate Tax Payable for certain Tax Periods"),
    (5, "2025-05-01", "Investors in REITs", T_INV,
     "Taxation of investors in a Real Estate Investment Trust that is exempt from Corporate Tax as a Qualifying Investment Fund"),
    (6, "2025-07-02", "Waiver of late-registration penalty", T_PEN,
     "Waiver of Administrative Penalty for failing to submit a Corporate Tax registration application within a specified deadline"),
    (7, "2025-08-27", "Tax Groups: financial statements and audit", T_ACC,
     "Financial Statements and Related Audit Requirements for a Tax Group"),
    (8, "2025", "Family wealth management structures", T_INV, "Corporate Tax treatment of family wealth management structures"),
    (9, "2025-09-26", "Transitional rules: real estate developers", T_INC,
     "Application of the valuation method under the transitional rules as set out in Ministerial Decision No. 120 of 2023 on disposal of Qualifying Immovable Property by a real estate developer that is a Taxable Person"),
    (10, "2026-04-29", "Meaning of “director” and “officer”", T_INC,
     "Clarification of the terms “director” and “officer” for the purpose of payments to Connected Persons under Article 36 of the Corporate Tax Law"),
    (11, "2026-07-15", "Downward adjustments in the Tax Return", T_INC,
     "Downward adjustments made by a Taxable Person in the Tax Return to comply with the Corporate Tax Law"),
    (12, "2026-07-30", "AT1 instruments of banks", T_INC,
     "Corporate Tax treatment of payments made in respect of Additional Tier 1 instruments by banks"),
]

PUBLISHER = "Federal Tax Authority"


def _edition(src, issued, **kw):
    full = {4: issued + "-01-01", 7: issued + "-01-01", 10: issued}[len(issued)]
    ed = dict(id="fta", label="Text as published by the Federal Tax Authority", short="FTA text", date=full,
              src=src, current=True, publisher=PUBLISHER)
    ed.update(kw)
    return ed


def build():
    import guideparse as GP
    acts = []
    by_id = {}
    for no, yr, issued, name, topic, eff, title, ex in sorted(DECISIONS, key=lambda r: (r[2], r[0])):
        key = f"FTAD-{no}-{yr}"
        a = dict(
            id=key, slug=f"ftad-{no}-{yr}", group="fta", sub="decision", short=f"FTA Decision No. {no} of {yr}",
            name=name, subject=name, title=f"FTA Decision No. {no} of {yr} on " + title, topics=[topic],
            status="repealed" if ex.get("repealed_by") else "in_force", status_label=ex.get("status_label", "In force"),
            issued=issued, effective=eff, en_only=True,
            editions=[_edition(f"{key}_EN-FTA", issued)],
        )
        if ex.get("repealed_by"):
            a["repealed_by"] = ex["repealed_by"]
        if ex.get("note"):
            a["status_note"] = ex["note"]
        acts.append(a)
        by_id[key] = a
    for no, yr, issued, name, topic, title, note, rep_by in PENDING_DECISIONS:
        key = f"FTAD-{no}-{yr}"
        a = dict(
            id=key, slug=f"ftad-{no}-{yr}", group="fta", sub="decision", short=f"FTA Decision No. {no} of {yr}",
            name=name, subject=name, title=f"FTA Decision No. {no} of {yr} on " + title, topics=[topic],
            status="repealed", status_label="Repealed", issued=issued, effective="", en_only=True, editions=[],
            repealed_by=rep_by, status_note=note, pending=note,
        )
        acts.append(a)
        by_id[key] = a
    for a in list(by_id.values()):
        if a.get("repealed_by") and a["repealed_by"] in by_id:
            by_id[a["repealed_by"]].setdefault("repeals", [])
            if a["id"] not in by_id[a["repealed_by"]]["repeals"]:
                by_id[a["repealed_by"]]["repeals"].append(a["id"])

    for code, issued, name, topic, title, family in sorted(GUIDES, key=lambda r: r[2].lower()):
        key = f"FTAG-{code}"
        a = dict(
            id=key, slug=code.lower(), group="fta", sub="guide", short=f"{family} {code}", code=code, numlabel=code,
            name=name, subject=title, title=f"{family} {code}: {title}", topics=[topic], status="in_force", status_label="Current",
            issued=issued, effective="", en_only=True, guide=True,
            editions=[_edition(f"{code}_EN-FTA", issued, fmt="guide", gcfg=(dict(qbox=True) if code == "CTGTXR1" else None))],
        )
        acts.append(a)
    for no, issued, name, topic, title in CLARIFICATIONS:
        code = f"CTP{no:03d}"
        a = dict(
            id=f"FTAC-{code}", slug=code.lower(), group="fta", sub="clarification", short=f"Public Clarification {code}", code=code, numlabel=code,
            name=name, subject=title, title=f"Public Clarification {code}: {title}", topics=[topic], status="in_force", status_label="Current",
            issued=issued, effective="", en_only=True, guide=True,
            editions=[_edition(f"{code}_EN-FTA", issued, fmt="guide", gcfg=dict(GP.CLAR_CFG))],
        )
        acts.append(a)
    for key, issued, upto, title in PRIVATE:
        a = dict(
            id=f"FTAP-{key}", slug=f"private-clarifications-{key}", group="fta", sub="private",
            short=f"FTA Private Clarifications (up to {upto})", code=f"PC-{key}", numlabel=f"Issued up to {upto}",
            name="Summary of Private Clarifications", subject=f"Questions and answers on Corporate Tax, issued up to {upto}", title=title,
            topics=list(PRIVATE_TOPICS), status="in_force", status_label="Current", issued=issued, effective="", en_only=True, guide=True,
            editions=[_edition(f"FTAP-{key}_EN-FTA", issued, fmt="guide", gcfg=dict(PRIVATE_CFG))],
        )
        acts.append(a)
    return acts
