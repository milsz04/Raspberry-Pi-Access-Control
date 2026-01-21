import time
import os
import random
import json
import paho.mqtt.client as mqtt
from PIL import Image, ImageDraw, ImageFont
import board
import neopixel
import SSD1331 as SSD1331
import base64


BASE_PATH = "/home/pi/tests/lib/project_iot/"
DEFAULT_IMG = BASE_PATH + "default_view/corridor.jpg"
INTRUDERS_DIR = BASE_PATH + "intruders/"
CAPTURES_DIR = BASE_PATH + "captures/"
FONT_PATH = BASE_PATH + "Font.ttf"
SUB_TOPIC = "camera/request"
PUB_TOPIC = "camera/response"
SERVER_IP = "10.108.33.123"

is_alarm_active = False

pixels = neopixel.NeoPixel(board.D18, 8, brightness=0.5, auto_write=False)
disp = SSD1331.SSD1331()
disp.Init()
disp.clear()

def add_timestamp_to_image(image_path, label="LIVE"):
    """
    Opens an image, resizes it to fit the OLED display, and adds a timestamp and status label.

    Args:
        image_path (str): The system path to the image file.
        label (str): Text to display on the image (e.g., "LIVE" or "ALARM").

    Returns:
        PIL.Image.Image: The processed image object ready for display, or None if the file is missing.
    """
    if os.path.exists(image_path):
        img = Image.open(image_path).convert("RGB")
        img = img.resize((96, 64))
        draw = ImageDraw.Draw(img)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            font = ImageFont.truetype(FONT_PATH, 10)
        except:
            font = ImageFont.load_default()

        draw.rectangle([0, 0, 95, 12], fill="black")
        draw.text((0, 0), timestamp, font=font, fill="white")
        draw.text((65, 50), label, fill="red")
        return img
    return None

def trigger_alarm(client):
    """
    Activates the alarm sequence: lights up LEDs, picks a random 'intruder' image, 
    displays it, saves evidence locally, and sends the data to the server via MQTT.

    Args:
        client: The active MQTT client instance used to publish the response.

    Returns:
        None
    """
    global is_alarm_active
    print("ALARM! Intruder detected!")
    is_alarm_active = True

    pixels.fill((255, 255, 255))
    pixels.show()

    try:
        intruder_files = [f for f in os.listdir(INTRUDERS_DIR) if f.lower().endswith(('.jpg', '.jpeg'))]
        if intruder_files:
            random_intruder = random.choice(intruder_files)
            source_path = os.path.join(INTRUDERS_DIR, random_intruder)

            alarm_img = add_timestamp_to_image(source_path, label="ALARM")

            if alarm_img:
                disp.ShowImage(alarm_img, 0, 0)

                now_time = time.strftime('%d-%m-%Y- %H:%M:%S')
                save_name = f"evidence_{time.strftime('%d%m%Y_%H%M%S')}.jpg"
                full_save_path = os.path.join(CAPTURES_DIR, save_name)
                alarm_img.save(full_save_path, format="JPEG", quality=85)

                with open(full_save_path, "rb") as f:
                    encoded_string = base64.b64encode(f.read()).decode('utf-8')

                payload = {
                    "event": "INTRUDER_CAUGHT", 
                    "timestamp": now_time,
                    "filename": save_name,
                    "image_base64": encoded_string
                }

                client.publish(PUB_TOPIC, json.dumps(payload))
                print(f'Image send to the server": {save_name}')


    except Exception as e:
        print(f"Error: {e}")

    time.sleep(0.5)
    pixels.fill((0, 0, 0))
    pixels.show()

    time.sleep(5)
    is_alarm_active = False

def on_connect(client, userdata, flags, rc, properties=None):
    """
    Callback triggered when the client connects to the MQTT broker.

    Args:
        client : The client instance for this callback.
        userdata: The private user data as set in Client() or user_data_set().
        flags (dict): Response flags sent by the broker.
        rc (int): The connection result (0 is success).
        properties (mqtt.Properties).

    Returns:
        None
    """
    if rc == 0:
        print("Connected to the Server")
        client.subscribe(SUB_TOPIC)
    else:
        print(f"Connection failed: {rc}")

def on_message(client, userdata, msg):
    """
    Callback triggered when a message is received on a subscribed topic.

    Args:
        client: The client instance for this callback.
        userdata: The private user data as set in Client().
        msg: An instance of MQTTMessage (contains topic, payload, qos, retain).

    Returns:
        None
    """
    data = json.loads(msg.payload.decode())

    if data.get("command") == "CAPTURE":
        trigger_alarm(client)


def run_camera():
    """
    Initializes the MQTT client, establishes connection, and runs the main loop 
    to refresh the 'Live' view on the OLED display.

    Returns:
        None
    """
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(SERVER_IP, 1883, 60)
        client.loop_start()

        while True:
            if not is_alarm_active:
                live_img = add_timestamp_to_image(DEFAULT_IMG, label="LIVE")
                if live_img:
                    disp.ShowImage(live_img, 0, 0)

            time.sleep(1)
    except KeyboardInterrupt:
        client.loop_stop()
        pixels.fill((0, 0, 0))
        pixels.show()
        disp.clear()
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    run_camera()