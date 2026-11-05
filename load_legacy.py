"""Load Legacy Requests (government demand for equipment, parts, service) into demand.duckdb.

Reads the legacy-requests repo in place (LEGACY_DIR); writes nothing there.
  data/records.jsonl         council/state/federal sole-source filings (history)  -> ask kind=sole_source
  private/bundle/rows.json.gz open DLA DIBBS RFQs + SAM.gov sole-source notices    -> ask kind=rfq | notice
  data/eol/notices.json      OEM end-of-life notices                              -> eol_notice
  data/eol/installs.json     agencies whose filings name that family              -> install
  data/supply/*.jsonl        listings for sale (craigslist, govdeals, ...)         -> listing
  data/supply/matches.json   filing line -> listing exact part matches            -> ask_listing
"""
import glob, gzip, json, os
import pandas as pd
from db import h, connect, replace_pull, insert, counts, price_or_none
from lexicon import REGION

LEGACY = os.path.expanduser(os.environ.get("LEGACY_DIR", "~/Desktop/workspace/the-google-of-obsolete-infrastructure-parts"))
PULL_ID = os.environ.get("PULL_ID", "legacy-2026-10-15")
f = lambda *p: os.path.join(LEGACY, *p)
agency_id = lambda name, state: h("agency", name, state or "")
d = lambda s: pd.to_datetime(s, errors="coerce").date() if s else None

orgs, asks, items = {}, [], []

# 1. sole-source filings: one ask per (client, matter); each record is one line item
rec = [json.loads(l) for l in open(f("data/records.jsonl"))]
by_matter = {}
for r in rec:
    by_matter.setdefault((r["client"], r["matter_id"]), []).append(r)
for (client, mid), rows in by_matter.items():
    r0 = rows[0]
    oid = agency_id(r0["agency"], r0.get("state"))
    orgs[oid] = {"org_id": oid, "name": r0["agency"], "kind": "agency", "state": r0.get("state")}
    aid = h("legacy", client, mid)
    total = sum(x["price_usd"] for x in rows if isinstance(x.get("price_usd"), (int, float)))
    asks.append({"ask_id": aid, "source": r0["platform"], "kind": "sole_source", "org_id": oid, "office": None,
                 "title": r0.get("title"), "body": None, "city": None, "state": r0.get("state"),
                 "posted_on": d(r0.get("date")), "due_on": None, "amount_usd": total or None,
                 "amount_basis": "contract_total" if total else None,
                 "url": r0.get("legistar_url") or r0.get("source_url")})
    for x in rows:
        qty = x.get("quantity")
        items.append({"ask_id": aid, "line_no": int(str(x["id"]).rsplit("-", 1)[-1]) if str(x["id"]).rsplit("-", 1)[-1].isdigit() else len(items),
                      "part": x.get("part"), "manufacturer": x.get("manufacturer"), "model": x.get("model"),
                      "part_numbers": x.get("part_numbers") or [], "qty": qty if isinstance(qty, (int, float)) else None,
                      "price_usd": x.get("price_usd") if isinstance(x.get("price_usd"), (int, float)) else None,
                      "vendor": x.get("sole_source_vendor"), "reason": x.get("reason"),
                      "equipment_class": x.get("equipment_class"), "is_obsolete": x.get("is_obsolete"),
                      "lead_time": x.get("lead_time"), "_record_id": x["id"]})
record_to_ask = {it["_record_id"]: it["ask_id"] for it in items}

# 2. open asks: one ask per solicitation, one item per NSN line
rows = json.load(gzip.open(f("private/bundle/rows.json.gz")))["rows"]
by_sol = {}
for r in rows:
    by_sol.setdefault((r["source"], r["solicitation"] or r["id"]), []).append(r)
for (src, sol), rs in by_sol.items():
    r0 = rs[0]
    oid = agency_id(r0["agency"], None)
    orgs.setdefault(oid, {"org_id": oid, "name": r0["agency"], "kind": "agency", "state": None})
    aid = h("open", src, sol)
    asks.append({"ask_id": aid, "source": "dibbs" if src == "DLA DIBBS" else "sam", "kind": "rfq" if src == "DLA DIBBS" else "notice",
                 "org_id": oid, "office": r0.get("office"), "title": sol, "body": None, "city": None, "state": None,
                 "posted_on": d(r0.get("issued")), "due_on": d(r0.get("due")), "amount_usd": None, "amount_basis": None,
                 "url": r0.get("rfq_url")})
    for i, r in enumerate(rs):
        items.append({"ask_id": aid, "line_no": i, "part": r.get("part"), "nsn": r.get("nsn"),
                      "manufacturer": "; ".join(r.get("makers") or []) or None,
                      "part_numbers": [a["pn"] for a in r.get("approved") or [] if a.get("pn")],
                      "approved": json.dumps(r.get("approved") or []), "qty": r.get("qty"), "unit": r.get("unit"),
                      "last_paid": r.get("last_paid"), "last_paid_on": d(r.get("last_paid_date")), "last_qty": r.get("last_qty"),
                      "took_surplus": r.get("took_surplus"), "buyer_name": r.get("buyer_name"),
                      "buyer_email": r.get("buyer_email"), "buyer_phone": r.get("buyer_phone")})

ask = pd.DataFrame(asks)
ask.insert(1, "pull_id", PULL_ID)
ask["region"] = ask["state"].map(REGION)
item = pd.DataFrame(items).drop(columns=["_record_id"], errors="ignore")
item = item.drop_duplicates(["ask_id", "line_no"])
for c in ["nsn", "approved", "unit", "last_paid", "last_paid_on", "last_qty", "took_surplus", "buyer_name", "buyer_email",
          "buyer_phone", "vendor", "reason", "equipment_class", "is_obsolete", "lead_time", "price_usd", "model"]:
    if c not in item:
        item[c] = None
for c in ["qty", "last_qty", "last_paid", "price_usd"]:
    item[c] = pd.to_numeric(item[c], errors="coerce")
for c in ["is_obsolete", "took_surplus"]:
    item[c] = item[c].map(lambda v: v if isinstance(v, bool) else None).astype("boolean")

# 3. end-of-life notices and installs
notices = json.load(open(f("data/eol/notices.json")))
eol = pd.DataFrame([{"notice_id": h(n["family"], n.get("label"), n.get("legacy_date"), n.get("status")), "family": n["family"], "oem": n["oem"], "label": n.get("label"), "status": n.get("status"),
                     "legacy_date": d(n.get("legacy_date")), "support_until": n.get("support_until") or None,
                     "successor": n.get("successor"), "successor_kind": n.get("successor_kind"),
                     "catalogs": n.get("catalogs") or [], "url": n.get("url"), "quote": n.get("quote"),
                     "fetched": d(n.get("fetched"))} for n in notices]).drop_duplicates("notice_id")
inst = []
for i in json.load(open(f("data/eol/installs.json"))):
    oid = agency_id(i["agency"], i.get("state"))
    orgs.setdefault(oid, {"org_id": oid, "name": i["agency"], "kind": "agency", "state": i.get("state")})
    for c in i.get("cites", []):
        inst.append({"org_id": oid, "family": i["family"], "filing_url": c.get("url"), "filed_on": d(c.get("date")), "quote": c.get("quote")})
install = pd.DataFrame(inst)
for n in notices:
    oid = h("oem", n["oem"])
    orgs.setdefault(oid, {"org_id": oid, "name": n["oem"], "kind": "oem", "state": None})

# 4. supply listings and exact matches
lst = []
for path in glob.glob(f("data/supply/*.jsonl")):
    for line in open(path):
        x = json.loads(line)
        loc = x.get("location")
        lst.append({"listing_id": h(x.get("url")), "source": x.get("source"), "title": x.get("title"),
                    "manufacturer": x.get("manufacturer"), "model": (x.get("model") or "").strip() or None,
                    "part_number": x.get("part_number"), "price_usd": price_or_none(x.get("price")),
                    "location": loc[1] if isinstance(loc, list) else loc, "seen_on": d(x.get("seen_at")), "url": x.get("url")})
listing = pd.DataFrame(lst).drop_duplicates("listing_id")
al = []
for rid, ms in json.load(open(f("data/supply/matches.json"))).items():
    if rid in record_to_ask:
        for m in ms:
            al.append({"ask_id": record_to_ask[rid], "listing_id": h(m.get("url"))})
ask_listing = pd.DataFrame(al).drop_duplicates()
known = set(listing["listing_id"])
extra = [m for rid, ms in json.load(open(f("data/supply/matches.json"))).items() for m in ms if h(m.get("url")) not in known]
if extra:
    listing = pd.concat([listing, pd.DataFrame([{"listing_id": h(m.get("url")), "source": m.get("source"), "title": m.get("title"),
        "manufacturer": m.get("manufacturer"), "model": m.get("model"), "part_number": m.get("part_number"),
        "price_usd": price_or_none(m.get("price")), "location": m.get("location") if not isinstance(m.get("location"), list) else m["location"][1],
        "seen_on": d(m.get("seen_at")), "url": m.get("url")} for m in extra])]).drop_duplicates("listing_id")

org = pd.DataFrame(orgs.values())
for c in ["industry", "size", "rating", "url"]:
    org[c] = None
pull = pd.DataFrame([{"pull_id": PULL_ID, "source": "legacy-requests repo", "pulled_on": pd.Timestamp("2026-10-15").date(),
                      "note": "records.jsonl (sole-source filings), rows.json.gz (open DIBBS/SAM, built 2026-10-15), eol notices+installs, supply listings"}])

con = connect()
replace_pull(con, PULL_ID)
insert(con, "pull", pull); insert(con, "org", org, upsert=True); insert(con, "ask", ask); insert(con, "item", item)
insert(con, "eol_notice", eol, upsert=True)
con.execute("DELETE FROM install"); insert(con, "install", install)
insert(con, "listing", listing, upsert=True); insert(con, "ask_listing", ask_listing)
con.execute("CHECKPOINT")
counts(con)
