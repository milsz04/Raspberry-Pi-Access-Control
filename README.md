Documentation For Final IoT Project
Access Control System
1. Project Concept
The goal of this project is to design and implement a distributed
Smart Access Control System using multiple Raspberry Pi units. The
system provides secure entry authentication using RFID technology,
real-time visual and acoustic feedback, and centralized database
management. It also features an intrusion detection module that
captures photos of unauthorized access attempts.
2. System Architecture
The system is divided into three functional Raspberrys to
demonstrate inter-device communication and distributed processing:
Node Components used Primary Responsibility

RFID Reader (Raspberry 1)
1) RFID reader, LED array, Buzzercard reading, feedback.
   
Camera (Rasberry 2)
2) LED array, OLED display. ‘Video’ monitoring and intruder snapshot capture.

Server (Raspberry 3)
3) MQTT Broker, SQLite Database, Management GUI.

3. Program Flow
a) User puts the card near the RFID reader
b) RFID sends the request via MQTT to the server with the access
request
c) The server checks in the database if the card is authorized.
If the card is authorized:
I. The server sends back the response that the card is
authorized
II. RFID gets the response, flashed LEDs to green and makes
opening sound
III. The server saves the log of an access in the database
d) If the card is in not the database and is not authorized:
I. The server sends back the response that the card is not
authorized
II. RFID gets the response, flashes LEDs to red and makes
alarm sound
III. Also, server sends the request to make a photo of an
intruder
IV. The camera gets the request, makes a photo and sends it
back to the server
V. The server saves the log of the break-in attempt with the
photo path in the database, and the photo is saved in
some specified location.
