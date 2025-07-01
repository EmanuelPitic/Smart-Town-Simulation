import sys
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import time
import json
import threading
import multiprocessing
from multiprocessing import Process, Queue
import socket
import random
import os
import paho.mqtt.client as mqtt

app = Flask(__name__, static_folder='static')
app.secret_key = 'mqtt_controller_secret_key'

# Global queue for communication between processes
mqtt_queue = multiprocessing.Queue()

# Lists for vehicles and traffic lights
cars = ["test/mario", "test/luigi"]
traffic_lights = ["TrafficLight_1", "TrafficLight_2", "TrafficLight_3"]


# MQTT Client class using paho-mqtt with MQTT 5
class MQTTClient:
    def __init__(self, broker_ip, broker_port, username, password):
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.username = username
        self.password = password

        # Create a paho-mqtt client using MQTTv5
        self.client = mqtt.Client(client_id=self.generate_client_id(), protocol=mqtt.MQTTv5)
        self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish

        # Set MQTT 5 properties if needed (optional)
        # For example, you can set a clean start, session expiry, etc.
        self.connect_properties = mqtt.Properties(mqtt.PacketTypes.CONNECT)
        self.connect_properties.SessionExpiryInterval = 0

    @staticmethod
    def generate_client_id():
        try:
            device_name = os.environ.get('COMPUTERNAME')
            if device_name:
                device_name = device_name.replace('-', '').strip()
            else:
                device_name = f"Unknown{random.randint(0, 100)}"
            unique_id = ''.join(random.choice('0123456789abcdef') for _ in range(8))
            return f"{device_name}{unique_id}"
        except Exception as e:
            print(f"Error generating client ID: {str(e)}")
            return None

    def on_connect(self, client, userdata, flags, reasonCode, properties):
        print("Connected to MQTT Broker")
        # Optionally, you can subscribe to topics here

    def on_disconnect(self, client, userdata, reasonCode, properties):
        print("Disconnected from MQTT Broker")

    def on_publish(self, client, userdata, mid):
        print(f"Message {mid} published")

    def connect(self):
        # Connect using the specified broker IP and port
        self.client.connect(self.broker_ip, self.broker_port, keepalive=60)
        # Start the network loop in a separate thread
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish_message(self, topic, message, qos):
        # Publish the message with the specified QoS
        result = self.client.publish(topic, payload=message, qos=qos)
        status = result[0]
        if status == mqtt.MQTT_ERR_SUCCESS:
            print(f"Published message to {topic}")
        else:
            print(f"Failed to publish message to {topic}")


# Function to run the MQTT client in a separate process
def mqtt_process_function(broker_ip, broker_port, queue, username, password):
    print(f"[MQTT‐PROC] PID={os.getpid()} starting, broker={broker_ip}:{broker_port}, user={username}")
    sys.stdout = open("/tmp/mqtt_child_stdout.log", "a")
    sys.stderr = open("/tmp/mqtt_child_stderr.log", "a")


    try:
        # Create the MQTT client instance within this process
        mqtt_client = MQTTClient(broker_ip, broker_port, username, password)
        mqtt_client.connect()

        while True:
            # Check if there is a command in the queue
            if not queue.empty():
                destination, message = queue.get()
                if destination == "Client":
                    if message == "Terminate":
                        break
                    if isinstance(message, tuple):
                        if message[0] == "Publish":
                            topic = message[1]
                            msg_content = message[2]
                            qos_str = message[3]

                            # Determine QoS level from the provided string
                            qos = 0
                            if qos_str == "At least once":
                                qos = 1
                            elif qos_str == "Exactly once":
                                qos = 2

                            mqtt_client.publish_message(topic, msg_content, qos)
                        elif message[0] == "Disconnect":
                            break
            # Brief sleep to avoid busy waiting
            time.sleep(0.1)
    except Exception as e:
        print(f"Error in MQTT client operation: {e}")
    finally:
        mqtt_client.disconnect()
        print("MQTT client disconnected and process ending")


# Global variable for MQTT client process
client_process = None


def start_mqtt_client(username, password):
    global client_process
    # Instead of creating the client here, we pass the parameters to the process
    client_process = Process(target=mqtt_process_function,
                             args=("10.53.187.73", 5050, mqtt_queue, username, password))
    client_process.start()
    return True


def stop_mqtt_client():
    global client_process
    if client_process:
        mqtt_queue.put(("Client", "Terminate"))
        client_process.join(timeout=2)
        if client_process.is_alive():
            client_process.terminate()
        client_process = None


# Flask Routes
@app.route('/')
def login():
    if 'username' in session:
        return redirect(url_for('control_panel'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def process_login():
    username = request.form.get('username')
    password = request.form.get('password')

    if username and password:
        session['username'] = username
        session['password'] = password

        # Start MQTT client using Paho MQTT configured for MQTT 5
        start_mqtt_client(username, password)
        return redirect(url_for('control_panel'))
    else:
        return render_template('login.html', error="Username and password are required")


@app.route('/control_panel')
def control_panel():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('control_panel.html',
                           cars=cars,
                           traffic_lights=traffic_lights)


@app.route('/car_control')
def car_control():
    if 'username' not in session:
        return redirect(url_for('login'))
    selected_car = request.args.get('car', cars[0])
    return render_template('car_control.html',
                           cars=cars,
                           selected_car=selected_car)


@app.route('/traffic_light_control')
def traffic_light_control():
    if 'username' not in session:
        return redirect(url_for('login'))
    selected_tl = request.args.get('traffic_light', traffic_lights[0])
    return render_template('traffic_light_control.html',
                           traffic_lights=traffic_lights,
                           selected_tl=selected_tl)


@app.route('/send_command', methods=['POST'])
def send_command():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"})

    data = request.get_json()
    command_type = data.get('type')
    topic = data.get('topic')
    message = data.get('message')
    qos = data.get('qos', "At most once")

    print(f"Sending command: {command_type} to {topic} with message {message}")
    # Put message in queue for the MQTT client process
    mqtt_queue.put(("Client", (command_type, topic, message, qos)))
    return jsonify({"status": "success"})


@app.route('/logout')
def logout():
    stop_mqtt_client()
    session.clear()
    return redirect(url_for('login'))


@app.route('/templates/<template_name>')
def get_template(template_name):
    return render_template(template_name)


if __name__ == '__main__':
    try:
        app.run(debug=True,use_reloader=False, host='0.0.0.0', port=5000)
    finally:
        stop_mqtt_client()
