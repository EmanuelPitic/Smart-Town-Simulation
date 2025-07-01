from machine import Pin, ADC

class ADCwithPullUp(ADC):
    def __init__(self, gpio, adc_vref=3.3):
        self.gpio = gpio
        self.adc_vref=adc_vref
        adc_pin = Pin(gpio, mode=Pin.IN, pull=Pin.PULL_UP)
        super().__init__(adc_pin)
        adc_pin = Pin(gpio, mode=Pin.IN, pull=Pin.PULL_UP)
        
    def sample(self):
        self.adc_value = self.read_u16()
        # Convert the ADC value to voltage
        self.voltage = (self.adc_value / 65535) * self.adc_vref
        #print("ADC Value:", self.adc_value, "Voltage:", self.voltage)
        return self.voltage