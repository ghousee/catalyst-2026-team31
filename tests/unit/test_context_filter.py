"""Context filter must never leak another system's rows (the context-trap guarantee).

Runs context_where() against in-memory SQLite mirroring the fingerprint columns of
doc_chunk/heuristic in sql/schema.sql, so it needs no Docker.
"""
import sqlite3

import pytest

from backend.pipeline.retrieve import context_params, context_where

DDL = """
CREATE TABLE {t} (
  id TEXT PRIMARY KEY,
  system_id TEXT NOT NULL,
  version_id TEXT,
  site_id TEXT,
  all_versions BOOLEAN NOT NULL DEFAULT 0,
  all_sites BOOLEAN NOT NULL DEFAULT 0,
  CHECK ((version_id IS NULL) = all_versions),
  CHECK ((site_id IS NULL) = all_sites)
)"""

# (id, system, version, site, all_versions, all_sites)
DOC_CHUNKS = [
    ("doc:P-201-manual:4.2", "sys:P-201", "ver:P-201:v3", "site:plant-2", 0, 0),
    ("doc:P-201-manual:4.3", "sys:P-201", "ver:P-201:v3", "site:plant-2", 0, 0),
    ("doc:P-201-manual:1.0", "sys:P-201", None, None, 1, 1),      # all versions, all sites
    ("doc:P-201-v2-manual:4.2", "sys:P-201", "ver:P-201:v2", "site:plant-2", 0, 0),
    ("doc:P-305-manual:3.1", "sys:P-305", "ver:P-305:v1", "site:plant-2", 0, 0),
    ("doc:P-305-manual:1.0", "sys:P-305", None, "site:plant-2", 1, 0),
]
HEURISTICS = [
    ("ravi:h12", "sys:P-201", "ver:P-201:v3", "site:plant-2", 0, 0),
    ("ravi:h3", "sys:P-201", None, None, 1, 1),
    ("priya:h1", "sys:P-305", "ver:P-305:v1", "site:plant-2", 0, 0),
]

P305 = {"system": "sys:P-305", "version": "ver:P-305:v1", "site": "site:plant-2"}
P201 = {"system": "sys:P-201", "version": "ver:P-201:v3", "site": "site:plant-2"}


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    for t, rows in (("doc_chunk", DOC_CHUNKS), ("heuristic", HEURISTICS)):
        con.execute(DDL.format(t=t))
        con.executemany(f"INSERT INTO {t} VALUES (?,?,?,?,?,?)", rows)
    yield con
    con.close()


def fetch(con, table, ctx):
    sql = f"SELECT id, system_id FROM {table} WHERE {context_where(paramstyle='named')}"
    return con.execute(sql, context_params(ctx)).fetchall()


@pytest.mark.parametrize("table", ["doc_chunk", "heuristic"])
@pytest.mark.parametrize("ctx", [
    P305,
    {**P305, "version": None},          # version unresolved
    {**P305, "site": None},             # site unresolved
    {**P305, "version": "ver:P-201:v3"},  # mismatched version id must not open P-201
])
def test_p305_never_retrieves_p201(db, table, ctx):
    rows = fetch(db, table, ctx)
    assert all(sys == "sys:P-305" for _, sys in rows), rows


def test_p305_gets_its_own_chunks(db):
    ids = {i for i, _ in fetch(db, "doc_chunk", P305)}
    assert ids == {"doc:P-305-manual:3.1", "doc:P-305-manual:1.0"}


def test_p201_v3_includes_all_versions_excludes_v2(db):
    ids = {i for i, _ in fetch(db, "doc_chunk", P201)}
    assert ids == {"doc:P-201-manual:4.2", "doc:P-201-manual:4.3", "doc:P-201-manual:1.0"}
    assert {i for i, _ in fetch(db, "heuristic", P201)} == {"ravi:h12", "ravi:h3"}


def test_null_version_requires_all_versions_flag(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO doc_chunk VALUES ('doc:bad', 'sys:P-201', NULL, 'site:plant-2', 0, 0)")


@pytest.mark.parametrize("ctx", [None, {}, {"system": None, "version": "ver:P-305:v1"}])
def test_unresolved_system_refuses(ctx):
    with pytest.raises(ValueError):
        context_params(ctx)


def test_pyformat_for_psycopg():
    assert context_where("d") == ("d.system_id = %(system)s"
                                  " AND (d.version_id = %(version)s OR d.version_id IS NULL)"
                                  " AND (d.site_id = %(site)s OR d.site_id IS NULL)")
