import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time
import board
import neopixel
from enum import Enum
import threading
import paho.mqtt.client as mqtt
import json


# GPIO Config
LED_COUNT = 8
LED_PIN = board.D18
BUZZER_PIN = 23


#MQTT Config
SERVER_IP = "10.108.33.123"
SUB_TOPIC = "door/response"
PUB_TOPIC = "door/request"
main_client = mqtt.Client()


ledStrip = neopixel.NeoPixel(
                     board.D18,
                     8,
                     brightness=1.0/32,
                     auto_write=False)


class Color(Enum):
    RED = 1
    GREEN = 2


class Sound(Enum):
    SUCCESS = 1
    ALARM = 2

    
reader = SimpleMFRC522()
GPIO.setup(BUZZER_PIN, GPIO.OUT)


def buzzer_play(play_time, break_time):
    """
        Play the sound on the buzzer

        Args:
            play_time: duration in seconds of how much the buzzer should play the sound
            break_time: duration in seconds of how long the break should be after the sound
    """
    GPIO.output(BUZZER_PIN, False)
    time.sleep(play_time)
    GPIO.output(BUZZER_PIN, True)
    time.sleep(break_time)


def play_sound(type: Sound):
    """
        Handle buzzer sound

            Args:
                type: type of sound to play (SUCCESS or ALARM)
    """
    if type == Sound.SUCCESS:
        buzzer_play(0.1, 0.1)
        buzzer_play(0.05, 0.05)
        buzzer_play(0.05, 0.05)
        buzzer_play(0.05, 0.05)
    elif type == Sound.ALARM:
        buzzer_play(1, 0)


def set_leds(color: Color):
    """
        Handle LED animation of specified color

            Args:
                color: The color of the animation (GREEN or RED)
    """
    color_value = (0, 0, 0)
    if color == Color.RED:
        color_value = (255, 0, 0)
    elif color == Color.GREEN:
        color_value = (0, 255, 0)

    for j in range(8):
        ledStrip[j] = color_value
        ledStrip.show()
        time.sleep(0.1)
        ledStrip[j] = (0, 0, 0)
 
    ledStrip.fill(color_value)
    ledStrip.show()
    time.sleep(1)
    ledStrip.fill((0,0,0))
    ledStrip.show()


def on_connect(client, userdata, flags, rc):
    """
        Esential function for MQTT connection
    """
    main_client.subscribe(SUB_TOPIC)
    print("Connected to server!")


def on_message(client, userdata, msg):
    """
        Handles messages received via MQTT from the server
    """
    data = json.loads(msg.payload.decode())
    command = data.get("access")
    if command == True:
        print("Otrzymano komendę: OTWÓRZ")
        threading.Thread(target=set_leds, args=(Color.GREEN,), daemon=True).start()
        threading.Thread(target=play_sound, args=(Sound.SUCCESS,), daemon=True).start()
    elif command == False:
        print("Otrzymano: BRAK WSTĘPU")
        threading.Thread(target=set_leds, args=(Color.RED,), daemon=True).start()
        threading.Thread(target=play_sound, args=(Sound.ALARM,), daemon=True).start()


def rfid_thread_function():
    """
        Handles reading cards from RFID reader and sends the request to the server
    """
    try:
        while True:
            id, _ = reader.read()
            uid_hex = hex(id)[2:].upper()
            print(f"RFID read: {uid_hex}")
            payload = json.dumps({"uid": uid_hex})

            main_client.publish(PUB_TOPIC, payload)
            print(f"UID send: {uid_hex}")
            time.sleep(2)
    finally:
        GPIO.cleanup()

def main():
    """
        Main function of a program
    """
    print("Access Control System Initiated...")
    
    main_client.connect(SERVER_IP, 1883, 60)
    main_client.on_connect = on_connect
    main_client.on_message = on_message
    main_client.loop_start()

    thread = threading.Thread(target=rfid_thread_function, daemon=True)
    thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Closing the system...")
        main_client.loop_stop()
        main_client.disconnect()


if __name__ == "__main__":
    main()