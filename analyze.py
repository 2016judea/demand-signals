"""Turn raw postings into need-prevalence tables by sector x region.

A "need" is a requirement or offer a posting states in its text (a licence, a tool,
a shift, a bonus). Prevalence = share of deduped postings in the cell that state it.
Lift = region prevalence / sector national prevalence.
"""
import glob, json, re
from lexicon import TITLE, REGION, N, COMPILED
import pandas as pd

df = pd.concat([pd.read_parquet(p) for p in glob.glob("data/raw/*.parquet")], ignore_index=True)
raw_n = len(df)
df["description"] = df["description"].fillna("")
# One posting can surface under several metros/terms; keep the first sector it was queried under
# but dedupe within sector so a posting is counted once per sector.
df["key"] = df["job_url"].fillna(df["id"])
# Indeed matches loosely ("lineman" returns Line Cook). Keep a row in a sector only if its title fits the sector.
for sec_, rx in TITLE.items():
    m = (df["q_sector"] == sec_) & ~df["title"].fillna("").str.contains(rx, case=False, regex=True)
    df = df[~m]
df = df.drop_duplicates(["key", "q_sector"])
# region assigned by the posting's own state, not the metro queried (50mi radius can cross lines)
st = df["location"].fillna("").str.extract(r",\s*([A-Z]{2})(?:,|$)")[0]
df["region"] = st.map(REGION).fillna(df["q_region"])


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
