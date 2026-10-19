"""Loader helper tests against an in-memory DuckDB with the real schema; demand.duckdb is never opened.
Run: .venv/bin/python -m pytest tests"""
import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["DEMAND_DB"] = ":memory:"
import pandas as pd
import pytest
import db


@pytest.fixture
def con():
    return db.connect()


def load(c, pull_id):
    db.replace_pull(c, pull_id)
    db.insert(c, "pull", pd.DataFrame([{"pull_id": pull_id, "source": "x", "pulled_on": pd.Timestamp("2026-10-17").date(), "note": ""}]))
    db.insert(c, "ask", pd.DataFrame([{"ask_id": db.h(pull_id, "u1"), "pull_id": pull_id, "source": "craigslist", "kind": "job", "title": "cook"}]))
    db.insert(c, "job", pd.DataFrame([{"ask_id": db.h(pull_id, "u1"), "is_remote": False}]))
    db.insert(c, "ask_duty", pd.DataFrame([{"ask_id": db.h(pull_id, "u1"), "quote": "schedule staff", "ai_doable": True, "need": "scheduling"}]))


def test_rerunning_the_hiring_signals_pull_does_not_double_ask_duty(con):
    # ask_duty has no primary key. The loader deleted its rows AFTER replace_pull had removed the
    # asks it joined on, so the delete matched nothing and every rerun appended a second copy.
    load(con, "hiring-signals-2026-10-17")
    load(con, "hiring-signals-2026-10-17")
    assert con.execute("SELECT count(*) FROM ask_duty").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM job").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM ask").fetchone()[0] == 1


def test_replace_pull_only_touches_its_own_pull(con):
    load(con, "hiring-signals-2026-10-17")
    load(con, "jobs-2026-10-17")
    db.replace_pull(con, "jobs-2026-10-17")
    assert con.execute("SELECT list(pull_id) FROM pull").fetchone()[0] == ["hiring-signals-2026-10-17"]
    assert con.execute("SELECT count(*) FROM ask_duty").fetchone()[0] == 1


@pytest.mark.parametrize("raw,expect", [
    (1200.0, 1200.0), ("1200", 1200.0), (0, 0.0), (None, None), ("", None), ("$1,200", None), (float("nan"), None),
    (9223372036854775807, None), (9.223372036854776e+18, None),   # the int64 overflow sentinel a scraper emitted
])
def test_price_or_none(raw, expect):
    assert db.price_or_none(raw) == expect
