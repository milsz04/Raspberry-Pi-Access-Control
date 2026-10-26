"""Shared fixtures for the SmartGate test suite.

The production modules talk to Raspberry Pi hardware (GPIO, RFID reader,
NeoPixel LEDs, OLED display) and to an MQTT broker as soon as they are
imported. These fixtures replace all of that with in-memory fakes so the
business logic can be tested on any machine, without a Pi or a broker.
"""
import importlib
import json
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeMQTTClient:
    """Records everything a module does with its MQTT client."""

    def __init__(self, *args, **kwargs):
        self.published = []      # list of (topic, payload_dict)
        self.subscriptions = []  # whatever was passed to subscribe()
        self.connected_to = None
        self.on_connect = None
        self.on_message = None

    def connect(self, host, port=1883, keepalive=60):
        self.connected_to = (host, port)

    def subscribe(self, topic, *args, **kwargs):
        self.subscriptions.append(topic)

    def publish(self, topic, payload=None, *args, **kwargs):
        self.published.append((topic, json.loads(payload)))

    def published_on(self, topic):
        return [payload for t, payload in self.published if t == topic]

    def loop_forever(self):
        pass  # the real call blocks forever; returning lets server.py import

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass


class FakePixels:
    """Stand-in for neopixel.NeoPixel that remembers what was shown."""

    def __init__(self, pin=None, count=8, *args, **kwargs):
        self.values = [(0, 0, 0)] * count
        self.fills = []
        self.show_count = 0

    def __setitem__(self, index, value):
        self.values[index] = value

    def __getitem__(self, index):
        return self.values[index]

    def fill(self, color):
        self.fills.append(color)
        self.values = [color] * len(self.values)

    def show(self):
        self.show_count += 1


def make_message(topic, payload):
    """Build an object shaped like paho's MQTTMessage."""
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return SimpleNamespace(topic=topic, payload=raw)


@pytest.fixture
def mqtt_message():
    return make_message


# --------------------------------------------------------------------------- #
# Module stubs
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_paho(monkeypatch):
    paho = types.ModuleType("paho")
    mqtt = types.ModuleType("paho.mqtt")
    client = types.ModuleType("paho.mqtt.client")
    client.Client = FakeMQTTClient
    paho.mqtt = mqtt
    mqtt.client = client
    monkeypatch.setitem(sys.modules, "paho", paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", client)
    return client


@pytest.fixture
def fake_board_and_leds(monkeypatch):
    board = types.ModuleType("board")
    board.D18 = "D18"
    neopixel = types.ModuleType("neopixel")
    neopixel.NeoPixel = FakePixels
    monkeypatch.setitem(sys.modules, "board", board)
    monkeypatch.setitem(sys.modules, "neopixel", neopixel)


@pytest.fixture
def no_sleep(monkeypatch):
    """Make time.sleep instant and record the requested durations."""
    calls = []
    monkeypatch.setattr("time.sleep", lambda seconds: calls.append(seconds))
    return calls


def fresh_import(monkeypatch, name):
    """Import a module from scratch so its import-time setup runs on our fakes."""
    monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module(name)


# --------------------------------------------------------------------------- #
# Modules under test
# --------------------------------------------------------------------------- #
@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point DatabaseManager at a throwaway SQLite file instead of /home/pi/..."""
    import database_manager

    path = str(tmp_path / "test_database.db")
    monkeypatch.setattr(database_manager, "DB_FILE", path)
    return path


@pytest.fixture
def db(db_path):
    from database_manager import DatabaseManager

    return DatabaseManager()


@pytest.fixture
def server(fake_paho, db_path, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # server.py creates project/media/ relative to cwd
    return fresh_import(monkeypatch, "server")


@pytest.fixture
def reader(fake_paho, fake_board_and_leds, no_sleep, monkeypatch):
    gpio = MagicMock(name="RPi.GPIO")
    rpi = types.ModuleType("RPi")
    rpi.GPIO = gpio
    mfrc522 = types.ModuleType("mfrc522")
    mfrc522.SimpleMFRC522 = MagicMock(name="SimpleMFRC522")
    monkeypatch.setitem(sys.modules, "RPi", rpi)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", gpio)
    monkeypatch.setitem(sys.modules, "mfrc522", mfrc522)

    module = fresh_import(monkeypatch, "reader")
    gpio.reset_mock()  # forget the GPIO.setup() done at import time
    return module


@pytest.fixture
def camera(fake_paho, fake_board_and_leds, no_sleep, tmp_path, monkeypatch):
    ssd1331 = types.ModuleType("SSD1331")
    ssd1331.SSD1331 = MagicMock(name="SSD1331")
    monkeypatch.setitem(sys.modules, "SSD1331", ssd1331)

    module = fresh_import(monkeypatch, "camera")

    intruders = tmp_path / "intruders"
    captures = tmp_path / "captures"
    intruders.mkdir()
    captures.mkdir()
    monkeypatch.setattr(module, "INTRUDERS_DIR", str(intruders) + os.sep)
    monkeypatch.setattr(module, "CAPTURES_DIR", str(captures) + os.sep)
    monkeypatch.setattr(module, "DEFAULT_IMG", str(tmp_path / "corridor.jpg"))
    monkeypatch.setattr(module, "FONT_PATH", str(tmp_path / "missing_font.ttf"))
    return module


@pytest.fixture
def sample_jpeg():
    """Write a small JPEG to the given path and return the path."""
    from PIL import Image

    def _write(path, size=(320, 240), color=(40, 80, 120)):
        Image.new("RGB", size, color).save(path, format="JPEG")
        return str(path)

    return _write
