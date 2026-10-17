"""Apply sql/migrations/*.sql to the live DB in order (all are idempotent).

    python -m backend.graph.migrate
"""
import sys
from pathlib import Path

import psycopg

from backend import settings

MIGRATIONS = Path(__file__).resolve().parents[2] / "sql" / "migrations"


def main():
    with psycopg.connect(settings.DATABASE_URL, autocommit=True) as conn:
        for f in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(f.read_text(encoding="utf-8"))
            print("applied", f.name)


if __name__ == "__main__":
    sys.exit(main())
