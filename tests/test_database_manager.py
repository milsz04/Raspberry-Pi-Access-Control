"""Tests for the SQLite layer: users, access checks and the access log."""
import sqlite3

import pytest


def table_names(db):
    with db.get_connection() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {name for (name,) in rows}


def test_init_creates_users_and_access_logs_tables(db):
    assert {"users", "access_logs"} <= table_names(db)


def test_init_is_idempotent(db_path):
    from database_manager import DatabaseManager

    first = DatabaseManager()
    first.add_user("AAA", "Anna")
    DatabaseManager()  # second start-up must not wipe existing data

    assert first.get_all_users() == [("AAA", "Anna")]


def test_added_user_is_granted_access(db):
    db.add_user("4AA7744FD6", "Anna Kowalska")

    assert db.check_access("4AA7744FD6") is True


@pytest.mark.parametrize("uid", ["UNKNOWN", "", "4aa7744fd6", None])
def test_unknown_or_malformed_uid_is_denied(db, uid):
    db.add_user("4AA7744FD6", "Anna Kowalska")

    assert db.check_access(uid) is False


def test_adding_duplicate_uid_keeps_original_user(db):
    db.add_user("4AA7744FD6", "Anna Kowalska")
    db.add_user("4AA7744FD6", "Someone Else")

    assert db.get_all_users() == [("4AA7744FD6", "Anna Kowalska")]


def test_removed_user_loses_access(db):
    db.add_user("4AA7744FD6", "Anna Kowalska")
    db.remove_user("4AA7744FD6")

    assert db.check_access("4AA7744FD6") is False
    assert db.get_all_users() == []


def test_removing_unknown_user_does_nothing(db):
    db.add_user("AAA", "Anna")
    db.remove_user("BBB")

    assert db.get_all_users() == [("AAA", "Anna")]


def test_log_attempt_stores_uid_result_and_photo(db):
    db.log_attempt("BAD1", False, "evidence_01.jpg")

    (log_id, timestamp, uid, granted, photo) = db.get_logs()[0]
    assert (uid, granted, photo) == ("BAD1", 0, "evidence_01.jpg")
    assert timestamp is not None


def test_log_attempt_photo_defaults_to_none(db):
    db.log_attempt("GOOD1", True)

    assert db.get_logs()[0][4] is None


def test_log_attempt_without_uid_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.log_attempt(None, False, "evidence.jpg")


def test_get_logs_returns_newest_first(db):
    with db.get_connection() as conn:
        conn.executemany(
            "INSERT INTO access_logs (timestamp, card_uid, granted) VALUES (?, ?, ?)",
            [
                ("2026-01-15 08:00:00", "OLD", 1),
                ("2026-01-15 12:00:00", "NEW", 0),
                ("2026-01-15 10:00:00", "MID", 1),
            ],
        )

    assert [row[2] for row in db.get_logs()] == ["NEW", "MID", "OLD"]
