# Data model: `demand.duckdb`

**What organizations publicly say they need.** A job posting and a government
sole-source filing are the same shape of fact: an organization, on a date, stating
what it needs and what it will pay. So one core (`org` → `ask`), with a detail table
per kind of ask, plus the supply and scale tables that give an ask context.

```
pull ──< ask >── org (employer | agency | oem)
          │
          ├── job          (kind = job: pay range, type, remote)
          ├──< item        (kind = sole_source | rfq | notice: part, maker, PN, NSN, qty, last paid, buyer)
          ├──< ask_search >── search      (how a job was found: sector, term, metro)
          ├──< ask_need   >── need        (normalised requirement: licence, tool, shift, offer)
          └──< ask_listing >── listing    (supply: something for sale that matches)

eol_notice ── install >── org      (OEM says a line ends; agencies on record running it)
jolts                              (BLS openings: the real scale behind the job sample)
```

## Tables

| Table | Grain | Answers |
|---|---|---|
| `pull` | one load run | Where and when did these rows come from? Every `ask` carries its `pull_id`; reloading a pull replaces it, a new pull appends. |
| `org` | one organization | Who is asking? `kind`: employer, agency, oem. Employers keyed by name (Indeed has no stable id); agencies by name + state. |
| `ask` | one stated need | What, by whom, where, when, for how much? `kind`: job, sole_source, rfq, notice. `amount_basis` says what `amount_usd` means: hourly_pay (job midpoint, /2080 h), contract_total (filing). |
| `job` | one job ask | Pay range as posted, job type, remote. |
| `item` | one line of a procurement ask | The part/service, maker, model, part numbers, NSN, approved sources (JSON of cage/pn/maker), qty, sole-source vendor and reason, obsolete flag, last price paid, buyer contact. |
| `search` | one Indeed query | The sampling frame: sector × term × metro. |
| `ask_search` | job × query that returned it | Which sector(s) a job counts toward. `on_topic=false` = title failed the sector filter (Line Cook returned for "lineman"). |
| `ask_duty` | one duty line of a job ask | What step of work does the posting pay for, in its own words, and could a tool take it over? (hiring-signals only) |
| `need` / `ask_need` | lexicon entry / match | Does this ask state requirement X? Patterns live in `lexicon.py`; change one, reload. |
| `eol_notice` | one OEM end-of-life batch | Which product line stops selling on what date, its catalogs and successor. Cited by `url` + verbatim `quote`. |
| `install` | agency × family, per filing | Which agencies' own filings show they run that line. |
| `listing` / `ask_listing` | one item for sale / exact match | Supply side: craigslist, govdeals, publicsurplus, dealers; matched to filing lines by maker + exact part number. |
| `jolts` | one BLS value | Real openings by industry and region (thousands) and rates (%). |

## Views
- `job_sector` — one row per on-topic (job, sector), employer attached. Start here for job questions.
- `need_share` — share of a sector × region's jobs stating each need.
- `gov_item` — every procurement line with its agency, dates and URL.
- `open_ask` — asks with `due_on` today or later (DIBBS/SAM RFQs).

## Rules that keep it honest
- **Job sector sizes follow the sampling plan** (50 per search per metro), not the real mix of openings. Use `jolts` for scale.
- **`region`** is the ask's own state mapped to a Census region (`lexicon.REGION`), not the metro searched.
- **Sole-source filings are history; DIBBS/SAM rows are open asks.** Don't mix them in a "what's open" count.
- **Buyer contacts and last-paid prices back a paid product** (Legacy Requests open asks, $85). The DB stays local; never publish rows from `item` raw.

## Loaders
| Script | Source | Pull id |
|---|---|---|
| `pull.py` → `load_jobs.py` | Indeed via python-jobspy, `jolts.json` | `jobs-YYYY-MM-DD` |
| `load_hiring_signals.py` | `~/Desktop/workspace/hiring-signals` (Twin Cities Craigslist + Greenhouse/Lever/Ashby; read in place). Adds `ask_duty`: each posting's duty lines verbatim, AI-doable or not, canonical need | `hiring-signals-YYYY-MM-DD` |
| `load_legacy.py` | `~/Desktop/workspace/the-google-of-obsolete-infrastructure-parts` (read in place) | `legacy-YYYY-MM-DD` |
