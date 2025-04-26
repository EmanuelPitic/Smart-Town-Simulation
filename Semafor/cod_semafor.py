from machine import UART, Pin
import time

#wifi_RX=Pin(0) #se refera la GP0
#wifi_CSm=Pin(1)
#wifi_SCK=Pin(2)
#wifi_TX=Pin(3)
#GP4-- bluetooth tx
#GP5-- bluetooth rx

#m d1 ;m d2 ;s d1 r 10 y 5 g 10 ;s d2 r 10 y 5 g 10 ;i 10 ;
function_mode=3 # 1--manual, only one direction stays on ; 2--secvential, incepand de la directia data, cu timpii  trimisi sau default; 3-- inteligent,
direction="d2" #sau d2
red_time=7 #30
yellow_time=2 #5
green_time=5 #20
green_time_smart=5


UART_bluetooth_buffer=""
UART_sprit_message=[]
UART_new_message=False
UART_rx_bluetooth=Pin(5, Pin.IN)
UART_tx_bluetooth=Pin(4, Pin.OUT)
UART_bluetooth = UART(1, 9600, tx=UART_tx_bluetooth, rx=UART_rx_bluetooth)


def UART_bluetooth_interrupt_handle(pin):
    global UART_bluetooth, UART_bluetooth_buffer, UART_split_message, UART_new_message, direction, function_mode, red_time, yellow_time, green_time, green_time_smart
    if UART_bluetooth.any():
        UART_bluetooth_buffer=UART_bluetooth.read().decode()
        print(UART_bluetooth_buffer)
        UART_bluetooth.write("Echo: ".encode() + UART_bluetooth_buffer.encode())
        UART_split_message=UART_bluetooth_buffer.split(" ")
        UART_new_message=True
        if UART_split_message[0]=="m":
            function_mode=1
            if UART_split_message[1]=="d1":
                direction="d1"
                print('m d1')
            elif UART_split_message[1]=="d2":
                direction="d2"
                print('m d2')
            else:
                print("Mesaj Bluetooth: manual, directie invalida")
            
        elif UART_split_message[0]=="s":
            function_mode=2
            if UART_split_message[1]=="d1":
                direction="d1"
                print('s d1')
            elif UART_split_message[1]=="d2":
                direction="d2"
                print('s d2')
            else:
                print("Mesaj Bluetooth: secvential, directie invalida")
            
            if UART_split_message[2]=="r" and UART_split_message[3].isdigit():
                red_time=int(UART_split_message[3])
                print("red_time",red_time)
            
            if UART_split_message[4]=="y" and UART_split_message[5].isdigit():
                yellow_time=int(UART_split_message[5])
                print("yellow_time",yellow_time)
            
            if UART_split_message[6]=="g" and UART_split_message[7].isdigit():
                green_time=int(UART_split_message[7])
                print("green_time",green_time)

        elif UART_split_message[0]=="i":
            function_mode=3
            if UART_split_message[1].isdigit():
                green_time_smart=int(UART_split_message[1])
                print("green_time_smart",green_time_smart)
        UART_bluetooth_buffer=""

UART_rx_bluetooth.irq(trigger=Pin.IRQ_RISING, handler=UART_bluetooth_interrupt_handle)

green_light_d1=Pin(6, Pin.OUT)
yellow_light_d1=Pin(7, Pin.OUT)
red_light_d1=Pin(8, Pin.OUT)
green_light_d2=Pin(9, Pin.OUT)
yellow_light_d2=Pin(10, Pin.OUT)
red_light_d2=Pin(11, Pin.OUT)
senzor_d1_1=Pin(12, Pin.IN)
senzor_d1_2=Pin(13, Pin.IN)
senzor_d2_1=Pin(14, Pin.IN)
senzor_d2_2=Pin(15, Pin.IN)
     
def traffic_mode_manual():
    global UART_new_message, direction, green_light_d1, yellow_light_d1, red_light_d1, red_light_d2, yellow_light_d2, green_light_d2
    while UART_new_message==False:   
        if direction=="d1":
            green_light_d1.value(1)
            yellow_light_d1.value(0)
            red_light_d1.value(0)
            
            red_light_d2.value(1)
            yellow_light_d2.value(0)
            green_light_d2.value(0)
        
        elif direction=="d2":
            red_light_d2.value(0)
            yellow_light_d2.value(0)
            green_light_d2.value(1)
            
            green_light_d1.value(0)
            yellow_light_d1.value(0)
            red_light_d1.value(1)
            

def traffic_mode_secvential():
    global UART_new_message, direction, green_light_d1, yellow_light_d1, red_light_d1, red_light_d2, yellow_light_d2, green_light_d2
    global green_time, yellow_time, red_time
    print('Secvential')
    print(UART_new_message)
    while UART_new_message==False:
        if direction=="d1":
            green_light_d1.value(1)
            yellow_light_d1.value(0)
            red_light_d1.value(0)
            
            red_light_d2.value(1)
            yellow_light_d2.value(0)
            green_light_d2.value(0)
            
            if UART_new_message==True:
                break
            time.sleep(green_time)
            
            green_light_d1.value(0)
            yellow_light_d1.value(1)
            red_light_d1.value(0)
            
            red_light_d2.value(1)
            yellow_light_d2.value(0)
            green_light_d2.value(0)
            
            if UART_new_message==True:
                break
            time.sleep(yellow_time)
            
            
            
            green_light_d1.value(0)
            yellow_light_d1.value(0)
            red_light_d1.value(1)
            
            red_light_d2.value(0)
            yellow_light_d2.value(0)
            green_light_d2.value(1)
            
            if UART_new_message==True:
                break
            time.sleep(red_time-2*yellow_time)
            
            
            green_light_d1.value(0)
            yellow_light_d1.value(0)
            red_light_d1.value(1)
            
            red_light_d2.value(0)
            yellow_light_d2.value(1)
            green_light_d2.value(0)
            if UART_new_message==True:
                break
            time.sleep(yellow_time)
            
            
            
        elif direction=="d2":
            green_light_d2.value(1)
            yellow_light_d2.value(0)
            red_light_d2.value(0)
            
            red_light_d1.value(1)
            yellow_light_d1.value(0)
            green_light_d1.value(0)
            
            if UART_new_message==True:
                break
            time.sleep(green_time)
            
            green_light_d2.value(0)
            yellow_light_d2.value(1)
            red_light_d2.value(0)
            
            red_light_d1.value(1)
            yellow_light_d1.value(0)
            green_light_d1.value(0)
            
            if UART_new_message==True:
                break
            time.sleep(yellow_time)
            
            green_light_d2.value(0)
            yellow_light_d2.value(0)
            red_light_d2.value(1)
            
            red_light_d1.value(0)
            yellow_light_d1.value(0)
            green_light_d1.value(1)
            
            if UART_new_message==True:
                break
            time.sleep(red_time-2*yellow_time)
            
            
            green_light_d2.value(0)
            yellow_light_d2.value(0)
            red_light_d2.value(1)
            
            red_light_d1.value(0)
            yellow_light_d1.value(1)
            green_light_d1.value(0)
            if UART_new_message==True:
                break
            time.sleep(yellow_time)
            
            
        

def traffic_mode_inteligent(): #lucru cu float pentru imbunatatire perfomante
    global UART_new_message, green_light_d1, yellow_light_d1, red_light_d1, red_light_d2, yellow_light_d2, green_light_d2
    global senzor_d1_1, senzor_d1_2, senzor_d2_1, senzor_d2_1
    active_d1_seconds_left=0
    active_d2_seconds_left=0
    ok_d1=True
    ok_d2=True
    
    
    
    while UART_new_message==False:
        if (senzor_d1_1.value()==0 or senzor_d1_2.value()==0) and active_d2_seconds_left==0 and ok_d1==True:
            active_d1_seconds_left=green_time_smart
            ok_d1=False
        
        if active_d1_seconds_left >=1:
            green_light_d1.value(1)
            yellow_light_d1.value(0)
            red_light_d1.value(0)
            time.sleep(1)
            active_d1_seconds_left=active_d1_seconds_left-1

        if active_d1_seconds_left ==0:
            green_light_d1.value(0)
            yellow_light_d1.value(0)
            red_light_d1.value(1)
            ok_d1=True
            
        
        if (senzor_d2_1.value()==0 or senzor_d2_2.value()==0) and active_d1_seconds_left==0 and ok_d2==True:
            active_d2_seconds_left=green_time_smart
            ok_d2=False
            
        if active_d2_seconds_left>=1:
            red_light_d2.value(0)
            yellow_light_d2.value(0)
            green_light_d2.value(1)
            time.sleep(1)
            active_d2_seconds_left=active_d2_seconds_left-1
        
        if active_d2_seconds_left==0:
            red_light_d2.value(1)
            yellow_light_d2.value(0)
            green_light_d2.value(0)
            ok_d2=True



def main():
    global UART_new_message
    while True:
        print('While Here')
        print(function_mode)
        if function_mode==1:
            traffic_mode_manual()
        elif function_mode==2:
            traffic_mode_secvential()
        elif function_mode==3:
            traffic_mode_inteligent()
        else:
            print('Mode not recognized')
            return -1
        
        #yellow_light_d2.value(0)
        #yellow_light_d2.value(0)
        UART_new_message=False
        
        
if __name__ == "__main__":
    main()
    




