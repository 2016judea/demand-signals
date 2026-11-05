"""Load the hiring-signals sweep (Twin Cities Craigslist jobs + public Greenhouse/Lever/Ashby
boards, read in place from ~/Desktop/workspace/hiring-signals) into demand.duckdb.

Adds what the Indeed pull doesn't carry: each posting's duty lines, quoted verbatim,
classified AI-doable or not and mapped to a canonical need (table ask_duty). PULL_ID
defaults to hiring-signals-2026-10-17; same id replaces, a new one appends.
"""
import json, os, re
from pathlib import Path
import pandas as pd
from db import h, connect, replace_pull, insert, counts
from lexicon import REGION, COMPILED

PULL_ID = os.environ.get("PULL_ID", "hiring-signals-2026-10-17")
SRC = Path(os.environ.get("HS_DIR", Path.home() / "Desktop/workspace/hiring-signals")) / "data"

posts = []
for name in ("craigslist_postings.jsonl", "ats_postings.jsonl"):
    for line in (SRC / name).open():
        p = json.loads(line)
        p.setdefault("source", "craigslist")
        if p.get("section") == "art":  # Craigslist cat=art is merchandise, not jobs
            continue
        posts.append(p)
duties = [json.loads(l) for l in (SRC / "duties.jsonl").open()]
need_map = json.loads((SRC / "need_map.json").read_text())
emp_by_url = {}
for d in duties:
    if d.get("employer"):
        emp_by_url.setdefault(d["url"], d["employer"].strip())

rows = []
for p in posts:
    emp = emp_by_url.get(p["url"]) or (p.get("employer") if p["source"] != "craigslist" else None) or "(unnamed Craigslist poster)"
    loc = p.get("location", "") or ""
    st = "MN" if re.search(r"\bMN\b|minnesota|minneapolis|st\.? paul|twin cities|hennepin|ramsey|anoka|dakota|washington county", loc + " " + p["source"], re.I) or p["source"] == "craigslist" else None
    rows.append({"ask_id": h(PULL_ID, p["url"]), "pull_id": PULL_ID, "source": p["source"], "kind": "job",
                 "org_id": h("employer", emp), "office": None, "title": p["title"], "body": p.get("body", ""),
                 "city": loc.split(",")[0].strip() or None, "state": st, "region": REGION.get(st) if st else None,
                 "posted_on": pd.to_datetime((p.get("posted") or "")[:10], errors="coerce"), "due_on": None,
                 "amount_usd": None, "amount_basis": None, "url": p["url"], "_emp": emp})
ask = pd.DataFrame(rows).drop_duplicates("ask_id")
ask["posted_on"] = ask["posted_on"].dt.date
org = pd.DataFrame({"name": ask["_emp"].unique()})
org.insert(0, "org_id", [h("employer", n) for n in org["name"]])
org["kind"] = "employer"
ask = ask.drop(columns="_emp")
job = pd.DataFrame({"ask_id": ask["ask_id"], "job_type": None, "is_remote": False, "pay_min": None, "pay_max": None, "pay_interval": None})
text = (ask["title"].fillna("") + "\n" + ask["body"].fillna("")).tolist()
ask_need = pd.DataFrame([(a, h(k)) for k, rx in COMPILED.items() for a, t in zip(ask["ask_id"], text) if rx.search(t)],
                        columns=["ask_id", "need_id"]).drop_duplicates()
duty = pd.DataFrame([{"ask_id": h(PULL_ID, d["url"]), "quote": d["quote"], "ai_doable": bool(d["ai_doable"]),
                      "need": need_map.get((d.get("need") or "").lower().strip()) if d["ai_doable"] else None} for d in duties])
duty = duty[duty["ask_id"].isin(set(ask["ask_id"]))].drop_duplicates(["ask_id", "quote"])

con = connect()
replace_pull(con, PULL_ID)  # clears ask_duty too; a delete placed after this line found no asks left to join on
con.execute("INSERT INTO pull VALUES (?, ?, ?, ?)", [PULL_ID, "craigslist+greenhouse+lever+ashby", PULL_ID.split("signals-")[-1],
            "Twin Cities postings, last ~45 days; duties classified by claude -p sonnet (hiring-signals/scripts/classify.py)"])
insert(con, "org", org[~org["org_id"].isin([r[0] for r in con.execute("SELECT org_id FROM org").fetchall()])])
insert(con, "ask", ask)
insert(con, "job", job)
insert(con, "ask_need", ask_need)
insert(con, "ask_duty", duty)
print(len(ask), "asks,", len(duty), "duties,", int(duty["ai_doable"].sum()), "AI-doable")
counts(con)
