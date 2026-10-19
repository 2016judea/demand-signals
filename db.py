"""Shared helpers for loaders writing demand.duckdb."""
import hashlib, os
import duckdb

DB = os.environ.get("DEMAND_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "demand.duckdb"))
PULL_SCOPED = ["ask", "search", "jolts"]


def h(*parts):
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:16]


def connect():
    con = duckdb.connect(DB)
    con.execute(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")).read())
    return con


def replace_pull(con, pull_id):
    """Drop everything a previous load of this pull wrote, so re-running is idempotent."""
    ids = f"(SELECT ask_id FROM ask WHERE pull_id = '{pull_id}')"
    for t in ["job", "item", "ask_search", "ask_need", "ask_listing", "ask_duty"]:
        con.execute(f"DELETE FROM {t} WHERE ask_id IN {ids}")
    for t in PULL_SCOPED + ["pull"]:
        con.execute(f"DELETE FROM {t} WHERE pull_id = ?", [pull_id])


INT64_MAX = 2 ** 63 - 1


def price_or_none(v):
    """A price as a float, or None. A value at the int64 ceiling is a scraper's overflow sentinel
    (one Craigslist ask loaded as $9,223,372,036,854,775,807 and became the max of its category),
    never a price."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f >= INT64_MAX * 0.999:
        return None
    return f


def insert(con, table, df, upsert=False):
    if df is None or len(df) == 0:
        return
    con.register("_df", df)
    cols = ", ".join(df.columns)
    con.execute(f"INSERT {'OR REPLACE ' if upsert else ''}INTO {table} ({cols}) SELECT {cols} FROM _df")
    con.unregister("_df")


def counts(con):
    for t in ["pull", "org", "ask", "job", "item", "search", "ask_search", "need", "ask_need",
              "eol_notice", "install", "listing", "ask_listing", "jolts"]:
        print(f"{t:12s}", con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
