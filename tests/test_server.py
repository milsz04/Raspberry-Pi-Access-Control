"""Tests for the server node: access decisions, camera requests and logging."""
import base64
import os

from database_manager import DatabaseManager

AUTHORIZED_UID = "4AA7744FD6"
UNKNOWN_UID = "DEADBEEF00"
JPEG_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-data\xff\xd9"


def camera_response(filename="evidence_15012026_143005.jpg", data=JPEG_BYTES):
    return {
        "event": "INTRUDER_CAUGHT",
        "filename": filename,
        "image_base64": base64.b64encode(data).decode("utf-8"),
    }


def test_server_connects_to_local_broker_on_import(server):
    assert server.client.connected_to == ("localhost", 1883)


def test_on_connect_subscribes_to_door_requests_and_camera_responses(server):
    server.on_connect(server.client, None, {}, 0)

    topics = {topic for topic, _qos in server.client.subscriptions[0]}
    assert topics == {server.TOPIC_DOOR_REQUEST, server.TOPIC_CAMERA_RESPONSE}


def test_authorized_card_is_granted_and_logged(server, mqtt_message):
    server.db.add_user(AUTHORIZED_UID, "Anna Kowalska")

    server.on_message(server.client, None, mqtt_message("door/request", {"uid": AUTHORIZED_UID}))

    [response] = server.client.published_on("door/response")
    assert response["uid"] == AUTHORIZED_UID
    assert response["access"] is True
    assert isinstance(response["timestamp"], float)

    [log] = server.db.get_logs()
    assert (log[2], log[3], log[4]) == (AUTHORIZED_UID, 1, None)


def test_authorized_card_does_not_trigger_camera(server, mqtt_message):
    server.db.add_user(AUTHORIZED_UID, "Anna Kowalska")

    server.on_message(server.client, None, mqtt_message("door/request", {"uid": AUTHORIZED_UID}))

    assert server.client.published_on("camera/request") == []


def test_unknown_card_is_denied_and_camera_is_asked_for_a_photo(server, mqtt_message):
    server.on_message(server.client, None, mqtt_message("door/request", {"uid": UNKNOWN_UID}))

    assert server.client.published_on("camera/request") == [{"command": "CAPTURE"}]
    [response] = server.client.published_on("door/response")
    assert response["access"] is False
    assert server.last_intruder_uid == UNKNOWN_UID


def test_denied_attempt_is_logged_only_once_photo_arrives(server, mqtt_message):
    server.on_message(server.client, None, mqtt_message("door/request", {"uid": UNKNOWN_UID}))

    assert server.db.get_logs() == []


def test_photo_from_camera_is_saved_and_linked_to_denied_attempt(server, mqtt_message, tmp_path):
    server.on_message(server.client, None, mqtt_message("door/request", {"uid": UNKNOWN_UID}))
    server.on_message(server.client, None, mqtt_message("camera/response", camera_response()))

    saved = tmp_path / "project" / "media" / "evidence_15012026_143005.jpg"
    assert saved.read_bytes() == JPEG_BYTES

    [log] = server.db.get_logs()
    assert (log[2], log[3], log[4]) == (UNKNOWN_UID, 0, "evidence_15012026_143005.jpg")
    assert server.last_intruder_uid is None


def test_camera_response_without_image_is_ignored(server, mqtt_message):
    server.on_message(server.client, None, mqtt_message("door/request", {"uid": UNKNOWN_UID}))
    server.on_message(server.client, None, mqtt_message("camera/response", {"filename": "x.jpg"}))

    assert server.db.get_logs() == []
    assert server.last_intruder_uid == UNKNOWN_UID


def test_unsolicited_camera_response_does_not_crash_server(server, mqtt_message):
    server.on_message(server.client, None, mqtt_message("camera/response", camera_response()))

    assert server.db.get_logs() == []


def test_malformed_payload_is_ignored(server, mqtt_message):
    server.on_message(server.client, None, mqtt_message("door/request", b"not json"))

    assert server.client.published == []
    assert server.db.get_logs() == []


def test_full_flow_mixes_granted_and_denied_attempts(server, mqtt_message):
    server.db.add_user(AUTHORIZED_UID, "Anna Kowalska")

    server.on_message(server.client, None, mqtt_message("door/request", {"uid": AUTHORIZED_UID}))
    server.on_message(server.client, None, mqtt_message("door/request", {"uid": UNKNOWN_UID}))
    server.on_message(server.client, None, mqtt_message("camera/response", camera_response()))

    results = sorted((log[2], log[3]) for log in server.db.get_logs())
    assert results == [(AUTHORIZED_UID, 1), (UNKNOWN_UID, 0)]


def test_server_uses_the_patched_test_database(server, db_path):
    assert server.db.db_name == db_path
    assert os.path.exists(db_path)
    assert isinstance(server.db, DatabaseManager)
