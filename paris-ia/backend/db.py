"""Accès aux données : PostgreSQL si DATABASE_URL est défini (production), sinon SQLite (local)."""
import os
import pathlib
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE = pathlib.Path(__file__).resolve().parent.parent / "data" / "app.sqlite"

SCHEMA = [
    """create table if not exists users (
        id {pk}, email text unique not null, salt text not null, pw text not null,
        plan text not null default 'free', stripe_customer text, created bigint not null)""",
    """create table if not exists newsletter (
        id {pk}, email text unique not null, created bigint not null, source text)""",
    # Preuve des consentements donnés à la souscription (CGV, demande d'accès immédiat).
    """create table if not exists consents (
        id {pk}, user_id bigint not null, kind text not null, version text not null, created bigint not null)""",
]


class Duplicate(Exception):
    """Violation d'unicité (email déjà inscrit)."""


def _connect():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    con = sqlite3.connect(SQLITE)
    con.row_factory = sqlite3.Row
    return con


def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if DATABASE_URL else sql


def init() -> None:
    pk = "bigint generated always as identity primary key" if DATABASE_URL else "integer primary key"
    with _connect() as con:
        for stmt in SCHEMA:
            con.execute(stmt.format(pk=pk))


def one(sql: str, params=()):
    with _connect() as con:
        return con.execute(_sql(sql), params).fetchone()


def run(sql: str, params=()) -> None:
    with _connect() as con:
        con.execute(_sql(sql), params)


def insert(sql: str, params=()) -> int:
    """Insère une ligne et renvoie son id ; lève Duplicate si l'email existe déjà."""
    try:
        with _connect() as con:
            if DATABASE_URL:
                return con.execute(_sql(sql) + " returning id", params).fetchone()["id"]
            return con.execute(sql, params).lastrowid
    except sqlite3.IntegrityError as e:
        raise Duplicate from e
    except Exception as e:
        if type(e).__name__ == "UniqueViolation":
            raise Duplicate from e
        raise
