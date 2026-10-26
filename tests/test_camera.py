"""Tests for the camera node: image processing and the intruder alarm."""
import base64
import os
import re

import pytest
from PIL import Image

from conftest import FakeMQTTClient


def test_missing_image_returns_none(camera, tmp_path):
    assert camera.add_timestamp_to_image(str(tmp_path / "nope.jpg")) is None


def test_image_is_resized_for_the_96x64_oled(camera, tmp_path, sample_jpeg):
    path = sample_jpeg(tmp_path / "frame.jpg", size=(640, 480))

    img = camera.add_timestamp_to_image(path, label="LIVE")

    assert img.size == (96, 64)
    assert img.mode == "RGB"


def test_timestamp_bar_is_drawn_at_the_top(camera, tmp_path, sample_jpeg):
    path = sample_jpeg(tmp_path / "white.jpg", color=(255, 255, 255))

    img = camera.add_timestamp_to_image(path)

    bar = [img.getpixel((x, y)) for x in range(96) for y in range(13)]
    dark = sum(1 for pixel in bar if max(pixel) < 60)
    # The bar is black except where the white timestamp text is drawn...
    assert dark / len(bar) > 0.5
    # ...and the picture below it is left untouched.
    assert min(img.getpixel((10, 30))) > 200


def test_alarm_sends_intruder_photo_to_server(camera, sample_jpeg):
    sample_jpeg(os.path.join(camera.INTRUDERS_DIR, "intruder1.jpg"))
    client = FakeMQTTClient()

    camera.trigger_alarm(client)

    [payload] = client.published_on("camera/response")
    assert payload["event"] == "INTRUDER_CAUGHT"
    assert re.fullmatch(r"evidence_\d{8}_\d{6}\.jpg", payload["filename"])

    saved_path = os.path.join(camera.CAPTURES_DIR, payload["filename"])
    with open(saved_path, "rb") as f:
        assert base64.b64decode(payload["image_base64"]) == f.read()


def test_saved_evidence_is_a_valid_oled_sized_jpeg(camera, sample_jpeg):
    sample_jpeg(os.path.join(camera.INTRUDERS_DIR, "intruder1.jpg"))
    client = FakeMQTTClient()

    camera.trigger_alarm(client)

    [payload] = client.published_on("camera/response")
    with Image.open(os.path.join(camera.CAPTURES_DIR, payload["filename"])) as img:
        assert img.format == "JPEG"
        assert img.size == (96, 64)


def test_alarm_shows_photo_on_display_and_resets(camera, sample_jpeg):
    sample_jpeg(os.path.join(camera.INTRUDERS_DIR, "intruder1.jpg"))

    camera.trigger_alarm(FakeMQTTClient())

    camera.disp.ShowImage.assert_called_once()
    assert camera.pixels.fills == [(255, 255, 255), (0, 0, 0)]
    assert camera.is_alarm_active is False


def test_alarm_without_intruder_images_sends_nothing(camera):
    client = FakeMQTTClient()

    camera.trigger_alarm(client)

    assert client.published == []
    assert camera.is_alarm_active is False


def test_non_jpeg_files_are_not_used_as_evidence(camera, tmp_path):
    (tmp_path / "intruders" / "notes.txt").write_text("not an image")
    client = FakeMQTTClient()

    camera.trigger_alarm(client)

    assert client.published == []


def test_capture_command_triggers_alarm(camera, mqtt_message, monkeypatch):
    triggered = []
    monkeypatch.setattr(camera, "trigger_alarm", lambda client: triggered.append(client))
    client = FakeMQTTClient()

    camera.on_message(client, None, mqtt_message("camera/request", {"command": "CAPTURE"}))

    assert triggered == [client]


def test_other_commands_are_ignored(camera, mqtt_message, monkeypatch):
    triggered = []
    monkeypatch.setattr(camera, "trigger_alarm", lambda client: triggered.append(client))

    camera.on_message(FakeMQTTClient(), None, mqtt_message("camera/request", {"command": "STOP"}))

    assert triggered == []


@pytest.mark.parametrize("rc, expected", [(0, ["camera/request"]), (5, [])])
def test_on_connect_subscribes_only_on_success(camera, rc, expected):
    client = FakeMQTTClient()

    camera.on_connect(client, None, {}, rc)

    assert client.subscriptions == expected
