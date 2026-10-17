-- demand.duckdb: what organizations publicly say they need. See DATA_MODEL.md.

-- provenance
CREATE TABLE IF NOT EXISTS pull (pull_id TEXT PRIMARY KEY, source TEXT, pulled_on DATE, note TEXT);

-- who states the need
CREATE TABLE IF NOT EXISTS org (org_id TEXT PRIMARY KEY, name TEXT, kind TEXT,   -- employer | agency | oem
  state TEXT, industry TEXT, size TEXT, rating DOUBLE, url TEXT);

-- the need itself: a job posting, a sole-source filing, an open RFQ, a SAM notice
CREATE TABLE IF NOT EXISTS ask (ask_id TEXT PRIMARY KEY, pull_id TEXT, source TEXT, kind TEXT,  -- job | sole_source | rfq | notice
  org_id TEXT, office TEXT, title TEXT, body TEXT, city TEXT, state TEXT, region TEXT,
  posted_on DATE, due_on DATE, amount_usd DOUBLE, amount_basis TEXT,  -- hourly_pay | contract_total | last_paid_unit
  url TEXT);

-- detail for kind = job
CREATE TABLE IF NOT EXISTS job (ask_id TEXT PRIMARY KEY, job_type TEXT, is_remote BOOLEAN,
  pay_min DOUBLE, pay_max DOUBLE, pay_interval TEXT);

-- detail for procurement kinds: one row per thing asked for
CREATE TABLE IF NOT EXISTS item (ask_id TEXT, line_no INT, part TEXT, manufacturer TEXT, model TEXT,
  part_numbers TEXT[], nsn TEXT, approved JSON, qty DOUBLE, unit TEXT, price_usd DOUBLE,
  vendor TEXT, reason TEXT, equipment_class TEXT, is_obsolete BOOLEAN, lead_time TEXT,
  last_paid DOUBLE, last_paid_on DATE, last_qty DOUBLE, took_surplus BOOLEAN,
  buyer_name TEXT, buyer_email TEXT, buyer_phone TEXT, PRIMARY KEY (ask_id, line_no));

-- how a job ask was found (the sampling frame)
CREATE TABLE IF NOT EXISTS search (search_id TEXT PRIMARY KEY, pull_id TEXT, sector TEXT, term TEXT,
  metro TEXT, metro_region TEXT, n_returned INT);
CREATE TABLE IF NOT EXISTS ask_search (ask_id TEXT, search_id TEXT, on_topic BOOLEAN, PRIMARY KEY (ask_id, search_id));

-- duty lines quoted verbatim from a posting, classified (hiring-signals loader)
CREATE TABLE IF NOT EXISTS ask_duty (ask_id TEXT, quote TEXT, ai_doable BOOLEAN, need TEXT);

-- normalised requirements stated in ask text
CREATE TABLE IF NOT EXISTS need (need_id TEXT PRIMARY KEY, label TEXT, kind TEXT, pattern TEXT);
CREATE TABLE IF NOT EXISTS ask_need (ask_id TEXT, need_id TEXT, PRIMARY KEY (ask_id, need_id));

-- the step before an ask: an OEM says a product line is ending, and who runs it
CREATE TABLE IF NOT EXISTS eol_notice (notice_id TEXT PRIMARY KEY, family TEXT, oem TEXT, label TEXT, status TEXT,
  legacy_date DATE, support_until TEXT, successor TEXT, successor_kind TEXT, catalogs TEXT[],
  url TEXT, quote TEXT, fetched DATE);
CREATE TABLE IF NOT EXISTS install (org_id TEXT, family TEXT, filing_url TEXT, filed_on DATE, quote TEXT);

-- supply: things for sale that could meet an ask
CREATE TABLE IF NOT EXISTS listing (listing_id TEXT PRIMARY KEY, source TEXT, title TEXT, manufacturer TEXT,
  model TEXT, part_number TEXT, price_usd DOUBLE, location TEXT, seen_on DATE, url TEXT);
CREATE TABLE IF NOT EXISTS ask_listing (ask_id TEXT, listing_id TEXT, PRIMARY KEY (ask_id, listing_id));

-- scale: BLS JOLTS openings
CREATE TABLE IF NOT EXISTS jolts (label TEXT, period TEXT, value DOUBLE, unit TEXT, pull_id TEXT);

-- views ---------------------------------------------------------------------
-- one row per (job ask, sector) that is on topic
CREATE OR REPLACE VIEW job_sector AS
SELECT s.sector, a.*, j.job_type, j.is_remote, o.name AS employer, o.industry
FROM ask a JOIN job j USING (ask_id)
JOIN ask_search x USING (ask_id) JOIN search s USING (search_id)
LEFT JOIN org o USING (org_id)
WHERE x.on_topic
QUALIFY row_number() OVER (PARTITION BY a.ask_id, s.sector ORDER BY s.search_id) = 1;

-- share of a sector x region's postings stating each need
CREATE OR REPLACE VIEW need_share AS
WITH base AS (SELECT sector, region, ask_id FROM job_sector)
SELECT b.sector, b.region, n.kind, n.label,
  count(DISTINCT an.ask_id) AS with_need, count(DISTINCT b.ask_id) AS asks,
  round(count(DISTINCT an.ask_id) / count(DISTINCT b.ask_id), 3) AS share
FROM base b CROSS JOIN need n
LEFT JOIN ask_need an ON an.ask_id = b.ask_id AND an.need_id = n.need_id
GROUP BY ALL;

-- government procurement, one row per line item, agency attached
CREATE OR REPLACE VIEW gov_item AS
SELECT a.ask_id, a.kind, a.source, o.name AS agency, a.office, a.state, a.posted_on, a.due_on,
  a.title, i.* EXCLUDE (ask_id), a.url
FROM ask a JOIN item i USING (ask_id) LEFT JOIN org o USING (org_id);

-- open asks (due today or later)
CREATE OR REPLACE VIEW open_ask AS SELECT * FROM ask WHERE due_on >= current_date;
