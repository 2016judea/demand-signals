# demand-signals

**Report (private artifact):** https://claude.ai/artifact/YKHYU9YjvoP8stXsNtjBQe

What organizations publicly say they need, in one DuckDB (`demand.duckdb`, gitignored, rebuildable):
72,881 active US job postings across 30 sectors × 4 regions, plus Legacy Requests' government demand
(2,730 sole-source filings, 18.7k open DLA DIBBS/SAM RFQs, OEM end-of-life notices, 197k supply listings).
Model: [DATA_MODEL.md](DATA_MODEL.md). Skill: `~/.claude/skills/demand-signals`.

- `pull.py` — Indeed scrape via python-jobspy (resumable, `data/raw/`, gitignored)
- `load_jobs.py`, `load_legacy.py` — loaders into `demand.duckdb` (`db.py` helpers, `schema.sql`)
- `lexicon.py` — sector title filters, state→region, need regexes
- `analyze.py` → `needs.json`; `bullets.json` + `page_template.html` → `help-wanted-decoded.html`
