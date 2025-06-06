from machine import Pin
import _thread
import time
import network
from umqtt.simple import MQTTClient

class Car:
    def __init__(self):
        
        self.led = Pin("LED", mode=Pin.OUT)
        
        self.__client_id = "Mario" # eventual inlocuim cu adresa mac a pico-ului daca putem
        self.__broker_ip = "10.53.187.73"
        self.__broker_port = 5050
        self.__topic = b"test/mario" 
        self.__client = None
        
        # Seteaza reteaua WiFi si parola aici
        self.__SSID = "Emy"
        self.__PASSWORD = "123456789"

        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

        if not self.wlan.isconnected():
            print("Conectare la reteaua Wi-Fi...")
            self.wlan.connect(self.__SSID, self.__PASSWORD)
            while not self.wlan.isconnected():
                time.sleep(0.5)

        # Daca deja e conectat, afiseaza IP-ul
        if self.wlan.isconnected():
            print("Conectare reusita!")
            print("Configuratie retea:", self.wlan.ifconfig())

            try:
                self.__client = MQTTClient(self.__client_id, self.__broker_ip, self.__broker_port)
                self.__client.set_callback(self.sub_callback)
                self.__client.connect()
                print("Conectat la broker")

                self.__client.subscribe()
                self.__client.publish('test/mario', 'Hello')
                print("Subscribed la topic:", self.__topic)
                self.led.on()
            except Exception as e:
                print("Eroare MQTT:", e)
        else:
            print("Status WLAN:", self.wlan.status())  # cod numeric pentru stare
            print("Esec la conectare. Verifica SSID/parola/hotspot.")

        # Motorul din partea stanga
        self.motor_stg_pins = [Pin(18, Pin.OUT), Pin(19, Pin.OUT), Pin(20, Pin.OUT), Pin(21, Pin.OUT)]

        # Motorul din partea dreapta
        self.motor_drt_pins = [Pin(10, Pin.OUT), Pin(11, Pin.OUT), Pin(12, Pin.OUT), Pin(13, Pin.OUT)]

        self.step_sequence = [
            [1, 0, 0, 1],
            [1, 1, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 1]]

        # Inițializare variabile
        self.command = b'f'  # Direcția de deplasare a motorului
        self.emergency = 1  # Daca este 0, este in stare normala, altfel este in starea de urgenta
        self.mode = 'm'  # Mod de funcționare, implicit autonom
        self.stop_semaphore = False  # Semafor pentru oprirea thread-ului
        self.stop_lock = _thread.allocate_lock()
        self.stg_index = 0
        self.drt_index = 0

    # Funcție pentru a face un motor sa se miste
    def move_motor(self, direction='forward', steps=100, delay=0.02):
        # Pentru direcția dorita
        sequence = self.step_sequence if direction == 'forward' else list(reversed(self.step_sequence))

        for _ in range(steps):
            for step in sequence:
                for i in range(4):
                    # Motorul stang — normal
                    self.motor_stg_pins[i].value(step[i])
                    # Motorul drept — montat invers fizic => invers logic
                    self.motor_drt_pins[i].value(step[3 - i])
                time.sleep(delay)
    
    def move_left_with_ratio(self, direction='forward', steps=10, delay=0.01, ratio=2.4):
        sequence = self.step_sequence if direction == 'forward' else list(reversed(self.step_sequence))

        total_steps = steps * len(sequence)
        
        if self.stg_index > 300:
            self.stg_index = 0
            self.drt_index = 0

        ratio_counter = 0.0

        for _ in range(total_steps):
            step_stg = sequence[self.stg_index % len(sequence)]
            for i in range(4):
                self.motor_stg_pins[i].value(step_stg[i])
            print(f"[STG] step {self.stg_index} -> {step_stg}")

            ratio_counter += 1.0
            if ratio_counter >= ratio:
                ratio_counter -= ratio
                step_drt = sequence[self.drt_index % len(sequence)]
                for i in range(4):
                    self.motor_drt_pins[i].value(step_drt[3 - i])
                print(f"    [DRT] step {self.drt_index} -> {step_drt}")
                self.drt_index += 1

            self.stg_index += 1
            time.sleep(delay)

    def move_right_with_ratio(self, direction = 'backward', steps=10, delay=0.01, ratio=2.4):
        sequence = self.step_sequence if direction == 'forward' else list(reversed(self.step_sequence))
       
        total_steps = steps * len(sequence)
        
        if self.drt_index > 300:
            self.stg_index = 0
            self.drt_index = 0

        ratio_counter = 0.0

        for _ in range(total_steps):
            step_drt = sequence[self.drt_index % len(sequence)]
            for i in range(4):
                self.motor_drt_pins[i].value(step_drt[i])
            print(f"[DRT] step {self.drt_index} -> {step_drt}")

            ratio_counter += 1.0
            if ratio_counter >= ratio:
                ratio_counter -= ratio
                step_stg = sequence[self.stg_index % len(sequence)]
                for i in range(4):
                    self.motor_stg_pins[i].value(step_stg[3 - i])
                print(f"    [STG] step {self.stg_index} -> {step_stg}")
                self.stg_index += 1

            self.drt_index += 1
            time.sleep(delay)
    
    def sub_callback(self, topic, msg):
        self.command = msg[1:]
        print("Mesaj primit pe topic:", topic, "->", msg)
        
    # Funcție pentru miscarea inainte
    def move_forward(self, steps=1, delay=0.02):
        print("Se misca inainte")
        self.move_motor('forward', steps, delay)

    # Funcție pentru miscarea inapoi
    def move_backward(self, steps=1, delay=0.02):
        print("Se misca inapoi")
        self.move_motor('backward', steps, delay)

    def move_right(self, steps=1, delay=0.02):
        print("Face dreapta")
        # self.move_left_with_ratio('forward', steps, delay)
        self.move_left_with_ratio()

    def move_left(self, steps=1, delay=0.02):
        print("Face stanga")
        self.move_right_with_ratio(direction='backward')

    # Funcție pentru oprirea motoarelor
    def stop_motors(self):
        for pin in self.motor_stg_pins + self.motor_drt_pins:
            pin.value(0)  # Opreste motoarele prin setarea pinilor pe 0

    # Funcție principala care ruleaza continuu
    def run(self):
        if self.__client is not None:
            while True:
                self.__client.wait_msg_nonblocking()
                if self.command == b'e':
                    self.emergency = 1
                elif self.command == b'n':
                    self.emergency = 0
                if self.emergency == 0:
                    if self.command == b'f':
                        self.move_forward()
                    elif self.command == b'b':
                        self.move_backward()
                    elif self.command == b'l':
                        self.move_left()
                    elif self.command == b'r':
                        self.move_right()
                else:
                    self.stop_motors()


    # Modul autonom de funcționare
    def autonomous_function(self):
        while self.stop_semaphore:
            print("Thread-ul ruleaza...")

    # Citirea datelor de la senzorii IR
    def sensor_measure(self):
        pass

car = Car()
car.command = b'f'
car.run()

# _thread.start_new_thread(car.command())
