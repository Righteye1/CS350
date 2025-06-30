
from gpiozero import PWMLED, Button
from statemachine import StateMachine, State
from adafruit_ahtx0 import AHTx0
from board import SCL, SDA
import busio
from time import sleep
from datetime import datetime
import serial
from math import floor
import digitalio
import board as lcdBoard
import adafruit_character_lcd.character_lcd as characterlcd
from threading import Thread

DEBUG = True

# Components
redLED = PWMLED(18)
blueLED = PWMLED(23)

# Updated GPIO pins for buttons
modeButton = Button(24, bounce_time=0.3)  # Middle button
incButton = Button(12, bounce_time=0.3)   # Increase set point
decButton = Button(25, bounce_time=0.3)   # Decrease set point

# UART setup
try:
    ser = serial.Serial('/dev/serial0', 9600, timeout=1)
except:
    ser = None
    if DEBUG:
        print("WARNING: UART /dev/serial0 not found. Serial output disabled.")

# I2C temp sensor setup
i2c = busio.I2C(SCL, SDA)
sensor = AHTx0(i2c)

# LCD setup
class Display:
    def __init__(self):
        self.lcd_rs = digitalio.DigitalInOut(lcdBoard.D17)
        self.lcd_en = digitalio.DigitalInOut(lcdBoard.D27)
        self.lcd_d4 = digitalio.DigitalInOut(lcdBoard.D5)
        self.lcd_d5 = digitalio.DigitalInOut(lcdBoard.D6)
        self.lcd_d6 = digitalio.DigitalInOut(lcdBoard.D13)
        self.lcd_d7 = digitalio.DigitalInOut(lcdBoard.D26)
        self.lcd_columns = 16
        self.lcd_rows = 2
        self.lcd = characterlcd.Character_LCD_Mono(
            self.lcd_rs, self.lcd_en,
            self.lcd_d4, self.lcd_d5, self.lcd_d6, self.lcd_d7,
            self.lcd_columns, self.lcd_rows)
        self.lcd.clear()

    def update(self, message):
        self.lcd.clear()
        self.lcd.message = message

screen = Display()

# Thermostat state machine
class Thermostat(StateMachine):
    off = State(initial=True)
    heat = State()
    cool = State()

    toggle = off.to(heat) | heat.to(cool) | cool.to(off)

    def __init__(self):
        super().__init__()
        self.setPoint = 72
        self.currentTemp = 0
        self.endDisplay = False

    def readTemp(self):
        try:
            self.currentTemp = round(sensor.temperature * 1.8 + 32)
        except:
            self.currentTemp = -999
            if DEBUG:
                print("Temp read failed")

    def on_enter_heat(self):
        if DEBUG: print("* HEATING")
        self.updateLEDs()

    def on_enter_cool(self):
        if DEBUG: print("* COOLING")
        self.updateLEDs()

    def on_enter_off(self):
        redLED.off()
        blueLED.off()
        if DEBUG: print("* OFF")

    def toggleMode(self):
        self.toggle()

    def raiseSetPoint(self):
        if self.setPoint < 100:
            self.setPoint += 1
            if DEBUG: print(f"SetPoint: {self.setPoint}")
            self.updateLEDs()

    def lowerSetPoint(self):
        if self.setPoint > 40:
            self.setPoint -= 1
            if DEBUG: print(f"SetPoint: {self.setPoint}")
            self.updateLEDs()

    def updateLEDs(self):
        redLED.off()
        blueLED.off()

        if self.currentTemp == -999:
            return

        if self.current_state.id == "heat":
            if self.currentTemp < self.setPoint:
                redLED.pulse()
            else:
                redLED.value = 1
        elif self.current_state.id == "cool":
            if self.currentTemp > self.setPoint:
                blueLED.pulse()
            else:
                blueLED.value = 1

    def uartOutput(self):
        return f"{self.current_state.id},{self.currentTemp},{self.setPoint}"

    def runDisplay(self):
        alt = 0
        count = 0
        while not self.endDisplay:
            self.readTemp()
            line1 = datetime.now().strftime("%m/%d %H:%M:%S")
            if self.currentTemp == -999:
                line2 = "Sensor error"
            elif alt < 5:
                line2 = f"Temp: {self.currentTemp}F"
                alt += 1
            else:
                line2 = f"{self.current_state.id.upper()} @ {self.setPoint}F"
                alt = 0

            screen.update(line1 + "\n" + line2)

            if DEBUG:
                print(f"State: {self.current_state.id} | Temp: {self.currentTemp} | SetPoint: {self.setPoint}")
            if ser and count % 30 == 0:
                ser.write((self.uartOutput() + "\n").encode())
            count += 1
            sleep(1)

thermo = Thermostat()
Thread(target=thermo.runDisplay).start()

modeButton.when_pressed = thermo.toggleMode
incButton.when_pressed = thermo.raiseSetPoint
decButton.when_pressed = thermo.lowerSetPoint
