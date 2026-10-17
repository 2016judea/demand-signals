"""Load an Indeed pull (data/raw/*.parquet) + jolts.json into demand.duckdb.

PULL_ID defaults to jobs-2026-10-17. Same PULL_ID replaces; a new one appends.
"""
import glob, json, os
import pandas as pd
from db import h, connect, replace_pull, insert, counts
from lexicon import TITLE, REGION, N, COMPILED

PULL_ID = os.environ.get("PULL_ID", "jobs-2026-10-17")
PULLED_ON = PULL_ID.split("jobs-")[-1]

raw = pd.concat([pd.read_parquet(p) for p in glob.glob("data/raw/*.parquet")], ignore_index=True)
raw = raw[raw["id"].notna()].copy()
raw["company"] = raw["company"].fillna("(unknown)").str.strip()
raw["ask_id"] = [h(PULL_ID, i) for i in raw["id"]]
raw["search_id"] = [h(PULL_ID, s, t, m) for s, t, m in zip(raw.q_sector, raw.q_term, raw.q_metro)]

search = (raw.groupby(["search_id", "q_sector", "q_term", "q_metro", "q_region"]).size().reset_index(name="n_returned")
          .rename(columns={"q_sector": "sector", "q_term": "term", "q_metro": "metro", "q_region": "metro_region"}))
search.insert(1, "pull_id", PULL_ID)

org = (raw.sort_values("company_industry", na_position="last").drop_duplicates("company")
       [["company", "company_industry", "company_num_employees", "company_rating", "company_url"]]
       .rename(columns={"company": "name", "company_industry": "industry", "company_num_employees": "size",
                        "company_rating": "rating", "company_url": "url"}))
org.insert(0, "org_id", [h("employer", n) for n in org["name"]])
org.insert(2, "kind", "employer")
org["rating"] = pd.to_numeric(org["rating"], errors="coerce")

p = raw.drop_duplicates("id").copy()
st = p["location"].fillna("").str.extract(r",\s*([A-Z]{2})(?:,|$)")[0]
mult = {"yearly": 1 / 2080, "monthly": 12 / 2080, "weekly": 1 / 40, "daily": 1 / 8, "hourly": 1}
lo, hi = pd.to_numeric(p["min_amount"], errors="coerce"), pd.to_numeric(p["max_amount"], errors="coerce")
pay = ((lo + hi.fillna(lo)) / 2) * p["interval"].map(mult)
pay[(pay < 7) | (pay > 400)] = None
ask = pd.DataFrame({
    "ask_id": p["ask_id"], "pull_id": PULL_ID, "source": "indeed", "kind": "job",
    "org_id": [h("employer", c) for c in p["company"]], "office": None, "title": p["title"],
    "body": p["description"].fillna(""), "city": p["location"].fillna("").str.split(",").str[0].str.strip(),
    "state": st, "region": st.map(REGION).fillna(p["q_region"]),
    "posted_on": pd.to_datetime(p["date_posted"], errors="coerce").dt.date, "due_on": None,
    "amount_usd": pay.round(2), "amount_basis": "hourly_pay", "url": p["job_url"]})
job = pd.DataFrame({"ask_id": p["ask_id"], "job_type": p["job_type"],
                    "is_remote": p["is_remote"].astype(str).str.lower().eq("true"),
                    "pay_min": lo, "pay_max": hi, "pay_interval": p["interval"]})

xs = raw[["ask_id", "search_id", "q_sector", "title"]].drop_duplicates(["ask_id", "search_id"]).copy()
xs["on_topic"] = True
for sec, rx in TITLE.items():
    m = xs["q_sector"].eq(sec)
    xs.loc[m, "on_topic"] = xs.loc[m, "title"].fillna("").str.contains(rx, case=False, regex=True)
xs = xs[["ask_id", "search_id", "on_topic"]]

need = pd.DataFrame([{"need_id": h(k), "label": k, "kind": g, "pattern": pat} for k, (g, pat) in N.items()])
text = (ask["title"].fillna("") + "\n" + ask["body"]).tolist()
ask_need = pd.DataFrame([(a, h(k)) for k, rx in COMPILED.items() for a, t in zip(ask["ask_id"], text) if rx.search(t)],
                        columns=["ask_id", "need_id"])

j = json.load(open("jolts.json"))
jolts = pd.DataFrame([{"label": k, "period": f"{v[0]}-{v[1]}", "value": float(v[2]),
                       "unit": "percent" if k.startswith(("rate", "hire rate")) else "thousands", "pull_id": PULL_ID}
                      for k, v in j.items()])
pull = pd.DataFrame([{"pull_id": PULL_ID, "source": "indeed via python-jobspy", "pulled_on": pd.Timestamp(PULLED_ON).date(),
                      "note": "30-day window, 50 mi radius, 50 per search, 30 sectors x 21 metros; BLS JOLTS Aug 2026"}])

con = connect()
replace_pull(con, PULL_ID)
insert(con, "pull", pull); insert(con, "org", org, upsert=True); insert(con, "need", need, upsert=True)
insert(con, "ask", ask); insert(con, "job", job); insert(con, "search", search)
insert(con, "ask_search", xs); insert(con, "ask_need", ask_need); insert(con, "jolts", jolts)
con.execute("CHECKPOINT")
counts(con)
