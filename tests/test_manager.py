"""Tests for the Django admin panel views (dashboard stats, user management)."""
import json
import sys
import types

import pytest

django = pytest.importorskip("django")
from django.conf import settings  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.urls import path  # noqa: E402

# Minimal URL config so redirect("manage") resolves without the full Django project.
test_urls = types.ModuleType("smartgate_test_urls")
test_urls.urlpatterns = [path("manage/", lambda request: HttpResponse(), name="manage")]
sys.modules["smartgate_test_urls"] = test_urls

if not settings.configured:
    settings.configure(DEBUG=True, ROOT_URLCONF="smartgate_test_urls", ALLOWED_HOSTS=["*"])
    django.setup()

from django.test import RequestFactory  # noqa: E402

from conftest import fresh_import  # noqa: E402


@pytest.fixture
def manager(db_path, monkeypatch):
    module = fresh_import(monkeypatch, "manager")
    rendered = {}

    def fake_render(request, template, context):
        rendered["template"], rendered["context"] = template, context
        return HttpResponse()

    monkeypatch.setattr(module, "render", fake_render)
    module.rendered = rendered
    return module


@pytest.fixture
def rf():
    return RequestFactory()


def insert_log(db, timestamp, uid, granted, photo):
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO access_logs (timestamp, card_uid, granted, photo_path) VALUES (?, ?, ?, ?)",
            (timestamp, uid, granted, photo),
        )


def test_check_update_with_no_logs(manager, rf):
    response = manager.check_update(rf.get("/api/check_update/"))

    assert json.loads(response.content) == {"last_id": 0, "count": 0}


def test_check_update_reports_newest_log_id_and_count(manager, rf):
    insert_log(manager.db, "2026-01-15 08:00:00", "A", 1, None)
    insert_log(manager.db, "2026-01-15 09:00:00", "B", 0, "evidence.jpg")

    response = manager.check_update(rf.get("/api/check_update/"))

    assert json.loads(response.content) == {"last_id": 2, "count": 2}


def test_dashboard_counts_granted_and_denied_attempts(manager, rf):
    insert_log(manager.db, "2026-01-15 08:00:00", "A", 1, None)
    insert_log(manager.db, "2026-01-15 09:00:00", "B", 0, "evidence.jpg")
    insert_log(manager.db, "2026-01-15 10:00:00", "C", 0, "evidence2.jpg")

    manager.index(rf.get("/"))

    context = manager.rendered["context"]
    assert manager.rendered["template"] == "dashboard.html"
    assert context["stats"] == {"total": 3, "granted": 1, "denied": 2}
    assert context["latest_id"] == 3


def test_dashboard_trims_milliseconds_and_cleans_photo_paths(manager, rf):
    insert_log(manager.db, "2026-01-15 14:30:05.123", "A", 0, "None")

    manager.index(rf.get("/"))

    [log] = manager.rendered["context"]["logs"]
    assert log == {"time": "2026-01-15 14:30:05", "uid": "A", "granted": 0, "photo": None}


def test_dashboard_lists_registered_users(manager, rf):
    manager.db.add_user("AAA", "Anna")

    manager.index(rf.get("/"))

    assert manager.rendered["context"]["users"] == [{"uid": "AAA", "name": "Anna"}]


def test_add_user_post_creates_user_and_redirects(manager, rf):
    response = manager.add_user(rf.post("/add/", {"uid": "AAA", "name": "Anna"}))

    assert response.status_code == 302
    assert response.url == "/manage/"
    assert manager.db.check_access("AAA") is True


@pytest.mark.parametrize("data", [{"uid": "AAA"}, {"name": "Anna"}, {"uid": "", "name": "Anna"}])
def test_add_user_with_missing_fields_adds_nothing(manager, rf, data):
    manager.add_user(rf.post("/add/", data))

    assert manager.db.get_all_users() == []


def test_add_user_ignores_get_requests(manager, rf):
    manager.add_user(rf.get("/add/", {"uid": "AAA", "name": "Anna"}))

    assert manager.db.get_all_users() == []


def test_remove_user_post_revokes_access(manager, rf):
    manager.db.add_user("AAA", "Anna")

    response = manager.remove_user(rf.post("/remove/", {"uid": "AAA"}))

    assert response.status_code == 302
    assert manager.db.check_access("AAA") is False
