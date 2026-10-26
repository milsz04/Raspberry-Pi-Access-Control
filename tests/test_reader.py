"""Tests for the RFID reader node: card UIDs, buzzer patterns and LED feedback."""
from unittest.mock import call

import pytest


class StopReading(Exception):
    """Raised by the fake RFID reader to break out of the infinite read loop."""


class SyncThread:
    """Runs the target immediately instead of in a background thread."""

    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def feedback(reader, monkeypatch):
    """Capture which LED colour and sound on_message asks for."""
    calls = []
    monkeypatch.setattr(reader.threading, "Thread", SyncThread)
    monkeypatch.setattr(reader, "set_leds", lambda color: calls.append(color))
    monkeypatch.setattr(reader, "play_sound", lambda sound: calls.append(sound))
    return calls


def test_granted_response_shows_green_and_plays_success(reader, feedback, mqtt_message):
    reader.on_message(reader.main_client, None, mqtt_message("door/response", {"access": True}))

    assert feedback == [reader.Color.GREEN, reader.Sound.SUCCESS]


def test_denied_response_shows_red_and_plays_alarm(reader, feedback, mqtt_message):
    reader.on_message(reader.main_client, None, mqtt_message("door/response", {"access": False}))

    assert feedback == [reader.Color.RED, reader.Sound.ALARM]


@pytest.mark.parametrize("payload", [{}, {"access": "yes"}, {"access": None}])
def test_response_without_clear_decision_gives_no_feedback(reader, feedback, mqtt_message, payload):
    reader.on_message(reader.main_client, None, mqtt_message("door/response", payload))

    assert feedback == []


def test_alarm_is_one_long_beep(reader, no_sleep):
    reader.play_sound(reader.Sound.ALARM)

    assert reader.GPIO.output.call_args_list == [call(23, False), call(23, True)]
    assert no_sleep == [1, 0]


def test_success_is_four_short_beeps(reader, no_sleep):
    reader.play_sound(reader.Sound.SUCCESS)

    assert reader.GPIO.output.call_count == 8
    assert no_sleep == [0.1, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05]


@pytest.mark.parametrize(
    "color, rgb",
    [("GREEN", (0, 255, 0)), ("RED", (255, 0, 0))],
)
def test_led_animation_flashes_color_then_turns_off(reader, color, rgb):
    reader.set_leds(reader.Color[color])

    assert reader.ledStrip.fills == [rgb, (0, 0, 0)]
    assert reader.ledStrip.values == [(0, 0, 0)] * 8


def test_card_uid_is_sent_to_server_as_uppercase_hex(reader):
    reader.reader.read.side_effect = [(0x4AA7744FD6, "card text"), StopReading()]

    with pytest.raises(StopReading):
        reader.rfid_thread_function()

    assert reader.main_client.published == [("door/request", {"uid": "4AA7744FD6"})]


def test_gpio_is_cleaned_up_when_reading_stops(reader):
    reader.reader.read.side_effect = StopReading()

    with pytest.raises(StopReading):
        reader.rfid_thread_function()

    reader.GPIO.cleanup.assert_called_once()


def test_on_connect_subscribes_to_door_responses(reader):
    reader.on_connect(reader.main_client, None, {}, 0)

    assert reader.main_client.subscriptions == ["door/response"]
