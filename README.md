# job-needs

**Report (private artifact):** https://claude.ai/artifact/YKHYU9YjvoP8stXsNtjBQe

What US employers say they need, read from active Indeed postings (via JobSpy, free) across 30 sectors × 21 metros, with BLS JOLTS openings for scale.

- `pull.py` — scrape (resumable; one parquet per sector/term/metro in `data/raw/`, gitignored)
- `analyze.py` — need flags (regex lexicon), employer-level phrase lift, sector × region tables → `needs.json`
- `bullets.json` — hand-written need bullets, every number from `needs.json`
- `page_template.html` + `page_data.json` → `help-wanted-decoded.html`

Pulled 2026-10-17: 83,684 rows, 72,881 unique postings.
