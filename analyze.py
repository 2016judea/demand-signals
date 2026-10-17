"""Turn raw postings into need-prevalence tables by sector x region.

A "need" is a requirement or offer a posting states in its text (a licence, a tool,
a shift, a bonus). Prevalence = share of deduped postings in the cell that state it.
Lift = region prevalence / sector national prevalence.
"""
import glob, json, re
import pandas as pd

df = pd.concat([pd.read_parquet(p) for p in glob.glob("data/raw/*.parquet")], ignore_index=True)
raw_n = len(df)
df["description"] = df["description"].fillna("")
# One posting can surface under several metros/terms; keep the first sector it was queried under
# but dedupe within sector so a posting is counted once per sector.
df["key"] = df["job_url"].fillna(df["id"])
# Indeed matches loosely ("lineman" returns Line Cook). Keep a row in a sector only if its title fits the sector.
TITLE = {
    "Energy & utilities": r"line ?(man|men|worker|technician|apprentice)|lineworker|solar|power plant|plant operator|utility|utilities|substation|wind|energy|electric(al)? (distribution|transmission)|meter|gas|nuclear|operator",
    "Agriculture & food processing": r"farm|agri|harvest|crop|dairy|ranch|greenhouse|nursery|meat|poultry|processing|production|plant|packag|butcher|sanitation|food (production|processing|manufactur)|line worker|machine operator|operator|packer|slaughter|egg",
    "Childcare": r"child|daycare|day care|preschool|toddler|infant|teacher|nanny|early (childhood|learning)|caregiver|assistant",
    "Education": r"teach|para|special ed|educat|instruct|tutor|school|aide|behavior|classroom|professor|substitute|principal|counselor|interventionist",
    "Government & public safety": r"police|officer|security|guard|correction|detention|deputy|sheriff|patrol|dispatcher|jailer|public safety|firefight|trooper",
}
for sec_, rx in TITLE.items():
    m = (df["q_sector"] == sec_) & ~df["title"].fillna("").str.contains(rx, case=False, regex=True)
    df = df[~m]
df = df.drop_duplicates(["key", "q_sector"])
# region assigned by the posting's own state, not the metro queried (50mi radius can cross lines)
REGION = {}
for r, sts in {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}.items():
    for s in sts.split():
        REGION[s] = r
st = df["location"].fillna("").str.extract(r",\s*([A-Z]{2})(?:,|$)")[0]
df["region"] = st.map(REGION).fillna(df["q_region"])

N = {  # label -> (group, regex). Case-insensitive unless the pattern starts with (?-i)
    # credentials
    "Active RN license": ("Credential", r"rn licen[cs]e|registered nurse( \(rn\))? licen|licensed (as an? )?(registered nurse|rn)\b|licen[cs]e (as|to practice as) an? (registered nurse|rn)|compact (nursing )?licen|multi-?state licen"),
    "BLS / CPR / ACLS": ("Credential", r"\b(bls|acls|pals|cpr)\b"),
    "CNA / HHA certification": ("Credential", r"\b(cna|certified nursing assistant|hha|home health aide) (certif|licen|required)"),
    "LPN/LVN": ("Credential", r"\b(lpn|lvn)\b"),
    "CDL Class A": ("Credential", r"\b(class a cdl|cdl[- ]a\b|cdl class a)"),
    "CDL (any)": ("Credential", r"\bcdl\b"),
    "Clean driving record / MVR": ("Credential", r"(clean|good|acceptable|safe) driving record|\bmvr\b|motor vehicle record"),
    "Valid driver's license": ("Credential", r"valid driver'?s licen"),
    "Forklift certification": ("Credential", r"forklift (certif|licen|experience)|certified forklift"),
    "OSHA 10/30": ("Credential", r"\bosha[- ]?(10|30)\b"),
    "Journeyman / master licence": ("Credential", r"\bjourney(man|person)|master (electrician|plumber)|licensed (electrician|plumber)"),
    "EPA 608": ("Credential", r"\bepa (608|section 608|universal)"),
    "ASE certification": ("Credential", r"\base[- ]certif|\base certified"),
    "CPA": ("Credential", r"(?-i)\bCPA\b"),
    "Securities licences (SIE/6/7/63)": ("Credential", r"series (6|7|63|65|66)\b|\bSIE\b"),
    "Insurance producer licence": ("Credential", r"(property (and|&) casualty|p&c|life (and|&) health|producer'?s?) licen"),
    "Teaching certificate": ("Credential", r"teaching (certificat|licen|credential)|state certification in|certified teacher"),
    "Security clearance": ("Credential", r"security clearance|\bts/sci\b|top secret|secret clearance|clearance required"),
    "PE licence": ("Credential", r"(?-i)\bPE\b licen|professional engineer|\bP\.E\."),
    "PMP": ("Credential", r"(?-i)\bPMP\b"),
    "Food handler / ServSafe": ("Credential", r"servsafe|food handler"),
    "Guard card / armed licence": ("Credential", r"guard card|security (officer )?licen|armed (guard|security)"),
    "Pharmacy licence / PTCB": ("Credential", r"\bptcb\b|pharmacy technician (licen|certif|registration)|pharmacist licen|\bpharm\.?d\b"),
    "Social work licence (LCSW/LMSW)": ("Credential", r"\b(lcsw|lmsw|lpc|lmft|lpcc|lisw)\b"),
    "Bar admission": ("Credential", r"admitted to (practice|the bar)|bar admission|member (in good standing )?of the .{0,20}bar"),
    "Real estate licence": ("Credential", r"real estate licen"),
    "Cyber certs (Security+/CISSP)": ("Credential", r"security\+|cissp|cism|\bcisa\b|comptia"),
    "Cloud certs (AWS/Azure)": ("Credential", r"aws certified|azure (certif|administrator|fundamentals)|solutions architect.{0,10}certif"),
    # tools
    "Microsoft Office / Excel": ("Tool", r"\b(excel|microsoft office|ms office|office 365|microsoft 365)\b"),
    "Salesforce / CRM": ("Tool", r"\b(salesforce|hubspot|crm)\b"),
    "SAP / Oracle / NetSuite ERP": ("Tool", r"\b(sap|oracle|netsuite|dynamics 365|erp)\b"),
    "QuickBooks": ("Tool", r"quickbooks"),
    "Epic / Cerner EHR": ("Tool", r"\b(epic|cerner|meditech|ehr|emr|electronic (health|medical) record)"),
    "SQL": ("Tool", r"\bsql\b"),
    "Python": ("Tool", r"\bpython\b"),
    "Cloud (AWS/Azure/GCP)": ("Tool", r"\b(aws|azure|gcp|google cloud)\b"),
    "Kubernetes / Docker": ("Tool", r"kubernetes|docker|\bk8s\b|terraform"),
    "Tableau / Power BI": ("Tool", r"tableau|power ?bi|looker"),
    "AI / LLM / GenAI": ("Tool", r"\b(generative ai|gen ?ai|llms?|large language model|chatgpt|copilot|ai tools|ai-powered|machine learning|artificial intelligence)\b"),
    "AutoCAD / Revit / SolidWorks": ("Tool", r"autocad|revit|solidworks|civil 3d|\bcad\b"),
    "PLC / controls": ("Tool", r"\bplcs?\b|allen[- ]bradley|programmable logic"),
    "POS systems": ("Tool", r"\bpos\b|point of sale|toast|square"),
    "WMS / scanners / RF": ("Tool", r"\bwms\b|warehouse management system|rf scanner|rf gun|handheld scanner"),
    "Procore / construction software": ("Tool", r"procore|bluebeam|primavera|\bp6\b"),
    "Yardi / RealPage / AppFolio": ("Tool", r"yardi|realpage|appfolio|entrata|onesite"),
    "Workday / ADP / HRIS": ("Tool", r"\bhris\b|workday|\badp\b|ukg|paylocity|paycom"),
    "Hand & power tools": ("Tool", r"(hand|power) tools"),
    # conditions
    "Nights / overnight": ("Schedule", r"\b(night shift|nights|overnight|3rd shift|third shift|graveyard)\b"),
    "Weekends": ("Schedule", r"\bweekends?\b"),
    "Overtime": ("Schedule", r"\bovertime\b"),
    "12-hour shifts": ("Schedule", r"12[- ]?(hour|hr)s? shifts?|three 12|3x12"),
    "On-call": ("Schedule", r"\bon[- ]call\b"),
    "PRN / per diem": ("Schedule", r"\bprn\b|per diem"),
    "Travel required": ("Schedule", r"travel (required|up to|\d+%)|overnight travel|regional travel"),
    "Lift 50+ lbs": ("Physical", r"(lift|carry|move)[^.]{0,40}\b(50|55|60|70|75|80|100)\s*(lbs|pounds|lb)"),
    "Standing / on feet": ("Physical", r"stand(ing)? for (long|extended|prolonged)|on (your|their) feet|stand for \d+"),
    "Outdoors / weather": ("Physical", r"outdoor|all weather|inclement weather|extreme (heat|cold|temperatures)"),
    "Drug screen": ("Screening", r"drug (screen|test)|substance (test|screen)"),
    "Background check": ("Screening", r"background (check|screen|investigation)"),
    # offers
    "Sign-on bonus": ("Offer", r"sign[- ]?on bonus|signing bonus|hiring bonus|sign on bonus"),
    "Weekly / daily pay": ("Offer", r"weekly pay|paid weekly|daily pay|same[- ]day pay|instant pay|dailypay"),
    "Tuition / training paid": ("Offer", r"tuition (reimburse|assist)|paid training|we will train|will train|on[- ]the[- ]job training|apprenticeship"),
    "401(k) match": ("Offer", r"401\(?k\)? (match|with)|matching 401|employer match"),
    "Health benefits day one": ("Offer", r"(day one|day 1|first day) (benefits|health|medical|coverage)|benefits (start|begin|effective) (on )?(day one|day 1|the first)"),
    "Shift differential": ("Offer", r"shift diff|night diff|differential"),
    "Relocation": ("Offer", r"relocation (assistance|package|bonus|support)"),
    "Commission / bonus pay": ("Offer", r"(?<!joint )\bcommission(s|ed)?\b(?! on)|uncapped|\bote\b|on[- ]target earnings"),
    "Pension": ("Offer", r"\bpension\b|defined benefit"),
    "Employee discount": ("Offer", r"employee discount|associate discount"),
    "Equity / stock": ("Offer", r"\bequity\b|stock options|\brsus?\b|espp"),
    "Tips": ("Offer", r"\btips\b|gratuit"),
    # people / profile
    "Bilingual (Spanish)": ("Profile", r"bilingual|spanish"),
    "No experience / entry level": ("Profile", r"no experience (necessary|required|needed)|entry[- ]level|new grads? (welcome|encouraged)"),
    "High school / GED": ("Profile", r"high school diploma|\bged\b"),
    "Bachelor's degree": ("Profile", r"bachelor'?s|\bb\.?s\.?\b degree|\bba/bs\b|4[- ]year degree"),
    "Master's / advanced degree": ("Profile", r"master'?s degree|\bmba\b|\bphd\b|doctorate|advanced degree"),
    "5+ years experience": ("Profile", r"\b([5-9]|1[0-5])\+? (or more )?years"),
    "Leadership / supervise others": ("Profile", r"supervis(e|ing) (a team|staff|employees)|lead a team|direct reports|people management"),
    "Customer-facing": ("Profile", r"customer[- ]facing|client[- ]facing|excellent customer service"),
    "Remote": ("Mode", r"\bfully remote|100% remote|remote position|work from home|\bwfh\b"),
    "Hybrid": ("Mode", r"\bhybrid\b"),
}
COMPILED = {}
for k, (g, p) in N.items():
    flags = 0 if p.startswith("(?-i)") else re.I
    COMPILED[k] = re.compile(p.replace("(?-i)", ""), flags)

text = (df["title"].fillna("") + "\n" + df["description"]).tolist()
for k, rx in COMPILED.items():
    df[k] = [bool(rx.search(t)) for t in text]

# pay normalised to hourly
mult = {"yearly": 1 / 2080, "monthly": 12 / 2080, "weekly": 1 / 40, "daily": 1 / 8, "hourly": 1}
mid = (pd.to_numeric(df["min_amount"], errors="coerce") + pd.to_numeric(df["max_amount"], errors="coerce").fillna(pd.to_numeric(df["min_amount"], errors="coerce"))) / 2
df["pay_hr"] = mid * df["interval"].map(mult)
df.loc[(df.pay_hr < 7) | (df.pay_hr > 400), "pay_hr"] = None
df["Part-time role"] = df["job_type"].fillna("").str.contains("parttime")
feat_extra = ["Part-time role"]
df["remote_flag"] = df["is_remote"].astype(str).str.lower().eq("true")

feat = list(N) + ["Part-time role"]

STOP = set("""a an the and or of to in for with on at by from as is are be will our we you your this that it its their they
our who what all any can may must not have has more other such than into per via etc including within across able ability
strong excellent preferred required plus experience years year knowledge skills skill work working job position role team
please apply equal opportunity employer status gender race religion national origin disability veteran sexual orientation
benefits pay salary hour hours full time part company us new one two three e g i e related degree field""".split())
QUAL = re.compile(r"(qualif|requirement|what you.{0,10}(need|bring|have)|must have|you have|skills|experience|education|who you are|about you|license|certif)", re.I)

def req_text(desc):
    # keep lines under a qualifications-like heading; fall back to whole text
    out, on = [], False
    for line in desc.splitlines():
        l = line.strip()
        if not l:
            continue
        head = len(l) < 60 and (l.startswith("#") or l.startswith("**") or l.endswith(":"))
        if head:
            on = bool(QUAL.search(l))
            continue
        if on:
            out.append(l)
    return " ".join(out) if out else ""

TOK = re.compile(r"[a-z][a-z0-9+#/.-]*[a-z0-9+#]|[a-z]")
def grams(t):
    w = [x for x in TOK.findall(t.lower())]
    g = set()
    for n in (2, 3):
        for i in range(len(w) - n + 1):
            seg = w[i:i + n]
            if seg[0] in STOP or seg[-1] in STOP or sum(x in STOP for x in seg) > 1:
                continue
            g.add(" ".join(seg))
    return g

def ngram_lift(df):
    """Phrase prevalence counted once per EMPLOYER, so one company's boilerplate can't win."""
    from collections import Counter, defaultdict
    bag = defaultdict(set)
    for d, co, s_, r_ in zip(df["description"], df["company"].fillna("?"), df["q_sector"], df["region"]):
        g = grams(req_text(d))
        if g:
            bag[(s_, r_, co)] |= g
    # sector-level employer docs
    sec_docs = defaultdict(dict)
    for (s_, r_, co), g in bag.items():
        sec_docs[s_].setdefault(co, set()).update(g)
    tot = Counter(); n_tot = 0
    for s_, cos in sec_docs.items():
        for g in cos.values(): tot.update(g); n_tot += 1
    res = {}
    for s_, cos in sec_docs.items():
        if len(cos) < 60: continue
        c = Counter()
        for g in cos.values(): c.update(g)
        n = len(cos); rows = []
        for g, k in c.items():
            p = k / n; q = (tot[g] - k + 1) / (n_tot - n + 1)
            if p >= 0.04 and k >= 12: rows.append((g, round(p, 3), round(p / q, 1)))
        rows.sort(key=lambda r: -(r[1] * min(r[2], 20)))
        entry = {"employers": n, "top": rows[:40], "regions": {}}
        for r in ["Northeast", "Midwest", "South", "West"]:
            rd = [g for (s2, r2, co), g in bag.items() if s2 == s_ and r2 == r]
            if len(rd) < 40: continue
            rc = Counter()
            for g in rd: rc.update(g)
            rest_n = sum(1 for (s2, r2, co) in bag if s2 == s_ and r2 != r)
            rest = Counter()
            for (s2, r2, co), g in bag.items():
                if s2 == s_ and r2 != r: rest.update(g)
            rr = []
            for g, k in rc.items():
                p = k / len(rd); q = (rest[g] + 1) / (rest_n + 1)
                if p >= 0.06 and k >= 6 and p / q >= 1.8: rr.append((g, round(p, 3), round(p / q, 1)))
            rr.sort(key=lambda x: -(x[1] * min(x[2], 10)))
            entry["regions"][r] = {"employers": len(rd), "top": rr[:20]}
        res[s_] = entry
    return res
out = {"raw_rows": raw_n, "postings": int(df["key"].nunique()), "sector_rows": len(df), "sectors": {}}
for sec, g in df.groupby("q_sector"):
    nat = g[feat].mean()
    s = {"n": len(g), "companies": int(g["company"].nunique()),
         "pay_med": round(g["pay_hr"].median(), 2) if g["pay_hr"].notna().sum() > 20 else None,
         "pay_share": round(g["pay_hr"].notna().mean(), 3),
         "top_titles": g["title"].str.replace(r"\s*[-–(|].*", "", regex=True).str.strip().value_counts().head(8).to_dict(),
         "top_companies": g["company"].value_counts().head(8).to_dict(),
         "industries": g["company_industry"].value_counts().head(5).to_dict(),
         "national": {k: round(v, 3) for k, v in nat.items() if v >= 0.03},
         "regions": {}}
    for reg, h in g.groupby("region"):
        if len(h) < 60:
            continue
        rp = h[feat].mean()
        lifts = {}
        for k in feat:
            # needs a real base and a real difference in points, not just a ratio of tiny numbers
            if rp[k] >= 0.05 and abs(rp[k] - nat[k]) >= 0.05 and (rp[k] / max(nat[k], 1e-9) >= 1.3 or rp[k] / max(nat[k], 1e-9) <= 0.7):
                lifts[k] = (round(rp[k], 3), round(nat[k], 3))
        s["regions"][reg] = {"n": len(h), "pay_med": round(h["pay_hr"].median(), 2) if h["pay_hr"].notna().sum() > 15 else None,
                             "diffs": lifts,
                             "top_companies": h["company"].value_counts().head(5).to_dict()}
    out["sectors"][sec] = s

# cross-sector region profile: same sampling design per region, so shares are comparable
reg_all = df.groupby("region")[feat].mean()
us_all = df[feat].mean()
out["region_profile"] = {}
for reg, row in reg_all.iterrows():
    out["region_profile"][reg] = {
        "n": int((df.region == reg).sum()),
        "pay_med": round(df.loc[df.region == reg, "pay_hr"].median(), 2),
        "over": {k: (round(row[k], 3), round(us_all[k], 3)) for k in feat if row[k] >= 0.04 and row[k] / us_all[k] >= 1.2},
        "under": {k: (round(row[k], 3), round(us_all[k], 3)) for k in feat if us_all[k] >= 0.04 and row[k] / us_all[k] <= 0.8},
    }
out["ngrams"] = ngram_lift(df)
out["us"] = {k: round(v, 3) for k, v in us_all.items()}
json.dump(out, open("needs.json", "w"), indent=1, default=str)
df.drop(columns=["description"]).to_parquet("postings_flags.parquet")
print(out["raw_rows"], "raw;", out["postings"], "unique postings;", len(out["sectors"]), "sectors")
