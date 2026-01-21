import json
import time
import base64
import os
import paho.mqtt.client as mqtt
from database_manager import DatabaseManager

BROKER = "localhost"
PORT = 1883

TOPIC_DOOR_REQUEST = "door/request"
TOPIC_DOOR_RESPONSE = "door/response"
TOPIC_CAMERA_REQUEST = "camera/request"
TOPIC_CAMERA_RESPONSE = "camera/response"
SAVE_DIR = "project/media/"

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

db = DatabaseManager()


last_intruder_uid = None

def on_connect(client, userdata, flags, rc):
    """
    Callback function triggered upon a successful connection to the MQTT broker.
    It subscribes the client to the necessary topics for door requests and camera responses.

    Args:
        client: The client instance for this callback.

    Returns:
        None
    """
    client.subscribe([(TOPIC_DOOR_REQUEST, 0), (TOPIC_CAMERA_RESPONSE, 0)])
    print(f"connected")

def on_message(client, userdata, msg):
    """
    Callback function triggered when a message is received on a subscribed topic.
    It handles logic for processing door access requests and saving images from the camera.

    Args:
        client: The client instance for this callback.
        msg: An instance of MQTTMessage, containing the topic and payload.

    Returns:
        None
    """
    global last_intruder_uid
    
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        
        if msg.topic == TOPIC_DOOR_REQUEST:
            card_uid = data.get("uid")
            print(f"UID: {card_uid}")

            has_access = db.check_access(card_uid)

            response = {
                "uid": card_uid,
                "access": has_access,
                "timestamp": time.time()
            }

            if has_access:
                print("Access granted")
                db.log_attempt(card_uid, True, None)
            else:
                print("Access denied ")
                
                last_intruder_uid = card_uid
                
                command_payload = {"command": "CAPTURE"}
                client.publish(TOPIC_CAMERA_REQUEST, json.dumps(command_payload))

            client.publish(TOPIC_DOOR_RESPONSE, json.dumps(response))

        elif msg.topic == TOPIC_CAMERA_RESPONSE:
            
            filename = data.get("filename", f"unknown_{int(time.time())}.jpg")
            img_base64 = data.get("image_base64")

            if img_base64:
                img_bytes = base64.b64decode(img_base64)
                full_path = os.path.join(SAVE_DIR, filename)
                
                with open(full_path, "wb") as f:
                    f.write(img_bytes)

                print(full_path)
                
                db.log_attempt(last_intruder_uid, False, filename)
                

                last_intruder_uid = None

    except Exception as e:
        print(f"Error: {e}")


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message


client.connect(BROKER, PORT, 60)
client.loop_forever()