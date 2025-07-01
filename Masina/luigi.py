from machine import Pin
import _thread
import time
import utime
import network
from umqtt.simple import MQTTClient
from umqtt.sensor import ADCwithPullUp

class Car:
    def __init__(self):
        
        self.led = Pin("LED", mode=Pin.OUT)
        
        self.__client_id = "Luigi" # eventual inlocuim cu adresa mac a pico-ului daca putem
        self.__broker_ip = "10.53.187.73"
        self.__broker_port = 5050
        self.__topic = b"test/luigi" 
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

        if self.wlan.isconnected():
            print("Conectare reusita!")
            print("Configuratie retea:", self.wlan.ifconfig())
            try:
                self.__client = MQTTClient(self.__client_id, self.__broker_ip, self.__broker_port)
                self.__client.set_callback(self.sub_callback)
                self.__client.connect()
                print("Conectat la broker")

                self.__client.subscribe()
                self.__client.publish('test/luigi', 'Hello')
                print("Subscribed la topic:", self.__topic)
                self.led.on()
            except Exception as e:
                print("Eroare MQTT:", e)
        else:
            print("Status WLAN:", self.wlan.status())  # cod numeric pentru stare
            print("Esec la conectare. Verifica SSID/parola/hotspot.")

        self.adcs = list(map(ADCwithPullUp, [28, 27]))
        self.LED_Ir = Pin(26, mode=Pin.OUT)
        self.LED_Ir.off()

        self.seq = [[1,1], [1,1], [1,1], [1,1], [1,1], [1,1], [1,1]]
        self.last_move = self.move_forward

        self.__d = None
        self.go = False
        self.last_obstacle_dist = 20
        self.last_semaphore_dist = 30
        self.last_detection_time = utime.ticks_ms()

        self.semaphore_trig = Pin(0, Pin.OUT) 
        self.semaphore_trig.value(0)
        self.semaphore_echo = Pin(1, Pin.IN, Pin.PULL_UP)

        self.obstacle_trig = Pin(16, Pin.OUT)
        self.obstacle_trig.value(0)
        self.obstacle_echo = Pin(17, Pin.IN, Pin.PULL_UP)

        self.motor_stg_pins = [Pin(18, Pin.OUT), Pin(19, Pin.OUT), Pin(20, Pin.OUT), Pin(21, Pin.OUT)]
        self.motor_drt_pins = [Pin(10, Pin.OUT), Pin(11, Pin.OUT), Pin(12, Pin.OUT), Pin(13, Pin.OUT)]

        self.step_sequence = [
            [1, 0, 0, 1],
            [1, 1, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 1]]

        # Inițializare variabile
        self.command = b'f'  # Direcția de deplasare a motorului
        self.emergency = 1  # Daca este 0, este in stare normala, altfel este in starea de urgenta
        self.mode = 'a'  # Mod de funcționare, implicit autonom
        self.stop_semaphore = False  # Semafor pentru oprirea thread-ului
        self.stop_lock = _thread.allocate_lock()
        self.stg_index = 0
        self.drt_index = 0

    def move_motor(self, direction='forward', steps=100, delay=0.003):
        sequence = self.step_sequence if direction == 'forward' else list(reversed(self.step_sequence))

        for _ in range(steps):
            for step in sequence:
                for i in range(4):
                    self.motor_stg_pins[i].value(step[i])
                    self.motor_drt_pins[i].value(step[3 - i])
                time.sleep(delay)
    
    def move_left_with_ratio(self, direction='forward', steps=10, delay=0.002, ratio=15):
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

            ratio_counter += 1.0
            if ratio_counter >= ratio:
                ratio_counter -= ratio
                step_drt = sequence[self.drt_index % len(sequence)]
                for i in range(4):
                    self.motor_drt_pins[i].value(step_drt[3 - i])
                self.drt_index += 1

            self.stg_index += 1
            time.sleep(delay)

    def move_right_with_ratio(self, direction = 'backward', steps=10, delay=0.002, ratio=15):
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

            ratio_counter += 1.0
            if ratio_counter >= ratio:
                ratio_counter -= ratio
                step_stg = sequence[self.stg_index % len(sequence)]
                for i in range(4):
                    self.motor_stg_pins[i].value(step_stg[3 - i])
                self.stg_index += 1

            self.drt_index += 1
            time.sleep(delay)
    
    def sub_callback(self, topic, msg):
        if topic == b'test/luigi':
            self.command = msg[1:]
            print("Mesaj primit pe topic:", topic, "->", msg)      
        elif topic == b'test/masini':
            print("Mesaj primit pe topic:", topic, "->", msg)
            d = msg[1:].decode("utf-8").split(' ')
            if self.__d == 'd1':
                if d[0] == 'r' and self.mode == 'a':
                    print('Rosu, stop')
                    self.emergecy = 1
                    self.go = False
                elif d[0] == 'g' and self.mode == 'a':
                    print('Green, go')
                    self.emergency = 0
                    self.go = True
            if self.__d == 'd2':
                if d[1] == 'r' and self.mode == 'a':
                    print('Rosu, stop')
                    self.emergecy = 1
                    self.go = False
                elif d[1] == 'g' and self.mode == 'a':
                    print('Green, go')
                    self.emergency = 0
                    self.go = True
        
    def move_forward(self, steps=1, delay=0.02):
        self.move_motor('forward', steps)

    def move_backward(self, steps=1, delay=0.02):
        self.move_motor('backward', steps, delay)

    def move_right(self, steps=1, delay=0.02):
        self.move_left_with_ratio()

    def move_left(self, steps=1, delay=0.02):
        self.move_right_with_ratio()

    def stop_motors(self):
        for pin in self.motor_stg_pins + self.motor_drt_pins:
            pin.value(0)

    def line_sensor(self):
        self.LED_Ir.on()
        time.sleep(0.002)
        A = list([x.sample() for x in self.adcs])
        self.LED_Ir.off()
        time.sleep(0.002)
        B = list([x.sample() for x in self.adcs])
        # print(list([(b-a) for a, b in zip(A, B)]), A, B)
        return list([0 if (b-a) > 1 else 1 for a, b in zip(A, B)])
    
    def update_sequence(self, new_step):
        self.seq.pop(0)          # elimină primul element
        self.seq.append(new_step) # adaugă noul pas
    
    def predominant_value(self):
        sum_0 = sum(step[0] for step in self.seq)
        sum_1 = sum(step[1] for step in self.seq)
        # pentru fiecare poziție, dacă suma > jumătate din 7 (adică 3.5), predomină 1, altfel 0
        pred_0 = 1 if sum_0 > 3 else 0
        pred_1 = 1 if sum_1 > 3 else 0
        return [pred_0, pred_1]

    def detect(self, trig, echo):
        trig.value(1)      # start trig
        utime.sleep_us(10)
        trig.value(0)        # porneste emisie US

        while echo()==0:
            start_t=utime.ticks_us() # in 1 iese cu ultima valoare
        while echo()==1:
            stop_t=utime.ticks_us() # in 0 iese cu ultima valoare

        durata=stop_t - start_t         # durata dus-intors ultrasunete
        dist= durata*342/2/10000      # in cm
        
        print("%.2f" % dist, "cm")    # afisare distanta
        return dist
    

    def autonomous_mode(self): 
        result = self.line_sensor() 
        self.update_sequence(result)
        res = self.predominant_value()
        # print(f'[{result[0]}, {result[1]}]')

        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, self.last_detection_time) > 1000:
            self.last_obstacle_dist = self.detect(self.obstacle_trig, self.obstacle_echo)
            self.last_semaphore_dist = self.detect(self.semaphore_trig, self.semaphore_echo)
            self.last_detection_time = current_time

        if self.last_obstacle_dist < 10:
            print('Sunt la semafor, nu stiu de ce ma opresc')
            self.stop_motors()
        elif self.last_semaphore_dist < 25 and self.go == False:
            print('Am vazut semafor si am rosu')
            self.stop_motors() 
        else:
            if self.last_semaphore_dist < 25 and self.go == True:
                print('Am vazut semafor, dar am verde')
            if res[0] == 1 and res[1] == 1:
                self.move_forward()
                self.last_move = self.move_forward
            elif res[0] == 0 and res[1] == 1:
                self.move_left()
                self.last_move = self.move_left
            elif res[0] == 1 and res[1] == 0:
                self.move_right() 
                self.last_move = self.move_right
            elif res[0] == 0 and res[1] == 0: 
                self.last_move()  
        return self.last_move
    
    def manual_mode(self):
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, self.last_detection_time) > 1000:
            self.last_obstacle_dist = self.detect(self.obstacle_trig, self.obstacle_echo)
            self.last_semaphore_dist = self.detect(self.semaphore_trig, self.semaphore_echo)
            self.last_detection_time = current_time

        if self.last_obstacle_dist < 10 or self.last_semaphore_dist < 12:
            self.stop_motors()
        else:
            if self.command == b'f':
                self.move_forward()
            elif self.command == b'b':
                self.move_backward()
            elif self.command == b'l':
                self.move_left()
            elif self.command == b'r':
                self.move_right()
        

    def run(self):
        if self.__client is not None:
            while True:
                self.__client.wait_msg_nonblocking()
                if self.command == b'e':
                    self.emergency = 1
                    self.stop_motors()
                elif self.command == b'n':
                    self.emergency = 0
                elif self.command == b'a':
                    self.mode = 'a'
                elif self.command == b'm':
                    self.mode = 'm'
                elif self.command == b'd1':
                    self.__d = 'd1'
                elif self.command == b'd2':
                    self.__d = 'd2'
                if self.mode == 'm':
                    if self.emergency == 0:
                        self.manual_mode()
                    else:
                        self.stop_motors()
                elif self.mode == 'a':
                    if self.emergency == 0:
                        self.last_move = self.autonomous_mode()
                        time.sleep(0.0005)
                    else:
                        self.stop_motors()

car = Car()
car.command = b'f'
car.run()