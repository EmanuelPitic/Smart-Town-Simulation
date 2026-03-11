import network
import time
import asyncio
from machine import Pin, UART
from umqtt.simple import MQTTClient


class UARTManager:
    def __init__(self):
        self.uart = UART(1, 9600, tx=Pin(4, Pin.OUT), rx=Pin(5, Pin.IN))
        self.buffer=""
    def any(self):
        return self.uart.any()

    def read(self):
        return self.uart.read()

    def write(self, msg):
        self.uart.write(msg)


class WiFiManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password

    def connect(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(self.ssid, self.password)
        print("Connecting to WiFi...", end="")
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(".", end="")
        if wlan.isconnected():
            print(f"\nWiFi connected! IP: {wlan.ifconfig()[0]}")
            return True
        else:
            print("\nFailed to connect to WiFi")
            return False


class MQTTManager:
    def __init__(self, client_id, broker, port, sub_topic, pub_topic, callback):
        self.client = MQTTClient(client_id, broker, port=port)
        self.sub_topic = sub_topic
        self.pub_topic = pub_topic
        self.callback = callback
        self.prev_published = None

    def connect(self):
        self.client.set_callback(self.callback)
        self.client.connect()
        self.client.subscribe()
        print(f"MQTT connected and subscribed to {self.sub_topic}")

    def check_msg(self):
        self.client.check_msg()

    def publish(self, msg):
        if msg != self.prev_published:
            try:
                self.client.publish(self.pub_topic.encode(), msg.encode())
                print(f"Published to {self.pub_topic}: '{msg}'")
                self.prev_published = msg
            except Exception as e:
                print("Publish error:", e)


class TrafficLight:
    def __init__(self, g, y, r):
        self.green = Pin(g, Pin.OUT)
        self.yellow = Pin(y, Pin.OUT)
        self.red = Pin(r, Pin.OUT)

    def set(self, g, y, r):
        self.green.value(g)
        self.yellow.value(y)
        self.red.value(r)

    def get_color(self):
        if self.green.value(): return 'g'
        if self.red.value(): return 'r'
        return 'y'

class Sensor:
    def __init__(self, pin):
        self.pin = Pin(pin, Pin.IN)

    def is_triggered(self):
        return self.pin.value() == 0


class TrafficController:
    def __init__(self):
        self.function_mode = 1
        self.direction = "d1"
        self.red_time = 7
        self.yellow_time = 2
        self.green_time = 5
        self.green_time_smart = 5
        self.new_mqtt_message = False
        self.uart = UARTManager()

        self.d1 = TrafficLight(6, 7, 8)
        self.d2 = TrafficLight(9, 10, 11)
        self.senzori = [Sensor(12), Sensor(13), Sensor(14), Sensor(15)]

    def update_from_command(self, parts):
        if parts[0] == "m":
            self.function_mode = 1
            if len(parts) > 1 and parts[1] in ["d1", "d2"]:
                self.direction = parts[1]
                print("Manual:", self.direction)
                self.uart.write(f"Mode set to manual, direction = {self.direction}\n".encode())
            else:
                self.uart.write(b"Invalid manual direction\n")

        elif parts[0] == "s":
            self.function_mode = 2
            msg = "Mode set to sequential"
            if len(parts) > 1 and parts[1] in ["d1", "d2"]:
                self.direction = parts[1]
                msg += f", direction = {self.direction}"
            if len(parts) >= 8:
                if parts[2] == "r" and parts[3].isdigit():
                    self.red_time = int(parts[3])
                    msg += f", red_time = {self.red_time}"
                if parts[4] == "y" and parts[5].isdigit():
                    self.yellow_time = int(parts[5])
                    msg += f", yellow_time = {self.yellow_time}"
                if parts[6] == "g" and parts[7].isdigit():
                    self.green_time = int(parts[7])
                    msg += f", green_time = {self.green_time}"
            print(msg)
            self.uart.write((msg + "\n").encode())

        elif parts[0] == "i":
            self.function_mode = 3
            if len(parts) > 1 and parts[1].isdigit():
                self.green_time_smart = int(parts[1])
                msg = f"Intelligent mode, green_time_smart = {self.green_time_smart}"
                print(msg)
                self.uart.write((msg + "\n").encode())
            else:
                self.uart.write(b"Invalid intelligent command\n")

        else:
            self.uart.write(b"Unknown command\n")

        self.new_mqtt_message = True

    def publish_state(self, mqtt):
        d1_color = self.d1.get_color()
        d2_color = self.d2.get_color()
        if d1_color in ('r', 'g') and d2_color in ('r', 'g'):
            mqtt.publish(f"{d1_color} {d2_color}")

    async def run_manual(self):
        while not self.new_mqtt_message:
            if self.direction == "d1":
                self.d1.set(1,0,0)
                self.d2.set(0,0,1)
            else:
                self.d2.set(1,0,0)
                self.d1.set(0,0,1)
            self.publish_state(app.mqtt)
            await asyncio.sleep_ms(100)

    async def run_sequential(self):
        print('Sequential mode started')
        while not self.new_mqtt_message:
            sets = [
                (1,0,0, 0,0,1, self.green_time),
                (0,1,0, 0,0,1, self.yellow_time),
                (0,0,1, 1,0,0, self.red_time - self.yellow_time),
                (0,0,1, 0,1,0, self.yellow_time)
            ] if self.direction == "d1" else [
                (0,0,1, 1,0,0, self.green_time),
                (0,0,1, 0,1,0, self.yellow_time),
                (1,0,0, 0,0,1, self.red_time - self.yellow_time),
                (0,1,0, 0,0,1, self.yellow_time)
            ]
            for d1g,d1y,d1r,d2g,d2y,d2r,duration in sets:
                self.d1.set(d1g,d1y,d1r)
                self.d2.set(d2g,d2y,d2r)
                self.publish_state(app.mqtt)
                if await self.async_wait(duration): return

    async def run_intelligent(self):
        active_d1, active_d2 = 0, 0
        ok_d1, ok_d2 = True, True
        self.d1.set(0,0,1)
        self.d2.set(0,0,1)
        while not self.new_mqtt_message:
            if (self.senzori[0].is_triggered() or self.senzori[1].is_triggered()) and active_d2 == 0 and ok_d1:
                active_d1 = self.green_time_smart
                ok_d1 = False
            if active_d1 > 0:
                self.d1.set(1,0,0)
                self.d2.set(0,0,1)
                self.publish_state(app.mqtt)
                await asyncio.sleep_ms(1000)
                active_d1 -= 1
            elif not ok_d1:
                self.d1.set(0,0,1)
                self.d2.set(0,0,1)
                self.publish_state(app.mqtt)
                ok_d1 = True
            if (self.senzori[2].is_triggered() or self.senzori[3].is_triggered()) and active_d1 == 0 and ok_d2:
                active_d2 = self.green_time_smart
                ok_d2 = False
            if active_d2 > 0:
                self.d2.set(1,0,0)
                self.d1.set(0,0,1)
                self.publish_state(app.mqtt)
                await asyncio.sleep_ms(1000)
                active_d2 -= 1
            elif not ok_d2:
                self.d2.set(0,0,1)
                self.d1.set(0,0,1)
                self.publish_state(app.mqtt)
                ok_d2 = True
            await asyncio.sleep_ms(100)

    async def async_wait(self, seconds):
        elapsed = 0.0
        while elapsed < seconds:
            if self.new_mqtt_message:
                return True
            await asyncio.sleep_ms(100)
            elapsed += 0.1
        return False

    async def uart_task(self):
        uart_buffer = ""
        while True:
            await asyncio.sleep_ms(100)
            if self.uart.any():
                try:
                    data = self.uart.read().decode()
                    print("Received raw Bluetooth:", data)
                    uart_buffer += data
                    if "\n" in uart_buffer:
                        lines = uart_buffer.split("\n")
                        for line in lines[:-1]:
                            cmd = line.strip()
                            if not cmd: continue
                            print("Bluetooth command:", cmd)
                            self.uart.write(b"Echo: " + cmd.encode() + b"\n")
                            self.update_from_command(cmd.split())
                        uart_buffer = lines[-1]
                except Exception as e:
                    print("UART read error:", e)
                    uart_buffer = ""


class App:
    def __init__(self):
        self.controller = TrafficController()
        self.wifi = WiFiManager("Emy", "123456789")
        self.mqtt = MQTTManager(
            MQTT_CLIENT_ID := "TrafficLight_1",
            MQTT_BROKER := "10.53.187.73",
            MQTT_PORT := 5050,
            MQTT_SUB_TOPIC := "TrafficLight_1",
            MQTT_PUB_TOPIC := "test/masini",
            callback=self.mqtt_callback
        )

    def mqtt_callback(self, topic, msg):
        time.sleep(1)
        try:
            print(f"Raw MQTT - Topic: {topic}, len: {len(msg)}, bytes: {msg}")
            message = msg[1:].decode('utf-8')
            message_clean = message.replace('\n', '').replace('\r', '').strip()
            print(f"Decoded & cleaned: '{message_clean}' (len {len(message_clean)})")
            if len(message_clean) == 0:
                print("ERROR: Message empty after cleaning")
                return
            self.controller.update_from_command(message_clean.split(" "))
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    async def main(self):
        if not self.wifi.connect():
            print("WiFi indisponibil, se pornește doar semaforul local (Bluetooth).")
            use_mqtt = False
        else:
            self.mqtt.connect()
            use_mqtt = True

        tasks = [
            asyncio.create_task(self.controller.uart_task()),
            asyncio.create_task(self.traffic_control_task()),
            asyncio.create_task(self.monitor_task())
        ]
        if use_mqtt:
            tasks.append(asyncio.create_task(self.mqtt_task()))
        await asyncio.gather(*tasks)

    async def traffic_control_task(self):
        while True:
            print(f"Traffic control mode: {self.controller.function_mode}")
            if self.controller.function_mode == 1:
                await self.controller.run_manual()
            elif self.controller.function_mode == 2:
                await self.controller.run_sequential()
            elif self.controller.function_mode == 3:
                await self.controller.run_intelligent()
            else:
                print("Mode not recognized")
                await asyncio.sleep_ms(1000)
            self.controller.new_mqtt_message = False
            await asyncio.sleep_ms(100)

    async def monitor_task(self):
        while True:
            print(f"System running — Mode: {self.controller.function_mode}, Direction: {self.controller.direction}")
            await asyncio.sleep_ms(10000)

    async def mqtt_task(self):
        while True:
            try:
                self.mqtt.check_msg()
                await asyncio.sleep_ms(100)
            except Exception as e:
                print("MQTT error:", e)
                await asyncio.sleep_ms(1000)

if __name__ == "__main__":
    app = App()
    asyncio.run(app.main())
