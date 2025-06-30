from gpiozero import Button, LED
from statemachine import StateMachine, State
from time import sleep
import board
import digitalio
import adafruit_character_lcd.character_lcd as characterlcd
from threading import Thread

DEBUG = True

class ManagedDisplay():
    def __init__(self):
        self.lcd_rs = digitalio.DigitalInOut(board.D17)
        self.lcd_en = digitalio.DigitalInOut(board.D27)
        self.lcd_d4 = digitalio.DigitalInOut(board.D5)
        self.lcd_d5 = digitalio.DigitalInOut(board.D6)
        self.lcd_d6 = digitalio.DigitalInOut(board.D13)
        self.lcd_d7 = digitalio.DigitalInOut(board.D26)

        self.lcd_columns = 16
        self.lcd_rows = 2
        self.lcd = characterlcd.Character_LCD_Mono(
            self.lcd_rs, self.lcd_en,
            self.lcd_d4, self.lcd_d5, self.lcd_d6, self.lcd_d7,
            self.lcd_columns, self.lcd_rows)

        self.lcd.clear()

    def cleanupDisplay(self):
        self.lcd.clear()
        self.lcd_rs.deinit()
        self.lcd_en.deinit()
        self.lcd_d4.deinit()
        self.lcd_d5.deinit()
        self.lcd_d6.deinit()
        self.lcd_d7.deinit()

    def clear(self):
        self.lcd.clear()

    def updateScreen(self, message):
        self.lcd.clear()
        self.lcd.message = message


class CWMachine(StateMachine):
    redLight = LED(18)
    blueLight = LED(23)
    message1 = 'SOS'
    message2 = 'OK'
    activeMessage = message1
    endTransmission = False

    off = State(initial=True)
    dot = State()
    dash = State()
    dotDashPause = State()
    letterPause = State()
    wordPause = State()

    screen = ManagedDisplay()

    morseDict = {
        "A": ".-", "B": "-...", "C": "-.-.", "D": "-..",
        "E": ".", "F": "..-.", "G": "--.", "H": "....",
        "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
        "M": "--", "N": "-.", "O": "---", "P": ".--.",
        "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
        "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
        "Y": "-.--", "Z": "--.."
    }

    doDot = off.to(dot)
    doDash = off.to(dash)
    doDDP = off.to(dotDashPause)
    doLP = off.to(letterPause)
    doWP = off.to(wordPause)

    backToOffFromDot = dot.to(off)
    backToOffFromDash = dash.to(off)
    backToOffFromDDP = dotDashPause.to(off)
    backToOffFromLP = letterPause.to(off)
    backToOffFromWP = wordPause.to(off)

    def on_enter_dot(self):
        if DEBUG:
            print("* Entering dot (red ON 500ms)")
        self.redLight.on()
        sleep(0.5)
        self.redLight.off()
        self.backToOffFromDot()

    def on_enter_dash(self):
        if DEBUG:
            print("* Entering dash (blue ON 1500ms)")
        self.blueLight.on()
        sleep(1.5)
        self.blueLight.off()
        self.backToOffFromDash()

    def on_enter_dotDashPause(self):
        if DEBUG:
            print("* Dot/dash pause 250ms")
        sleep(0.25)
        self.backToOffFromDDP()

    def on_enter_letterPause(self):
        if DEBUG:
            print("* Letter pause 750ms")
        sleep(0.75)
        self.backToOffFromLP()

    def on_enter_wordPause(self):
        if DEBUG:
            print("* Word pause 3000ms")
        sleep(3.0)
        self.backToOffFromWP()

    def toggleMessage(self):
        if self.activeMessage == self.message1:
            self.activeMessage = self.message2
        else:
            self.activeMessage = self.message1
        if DEBUG:
            print(f"* Toggled message to: {self.activeMessage}")

    def processButton(self):
        self.toggleMessage()

    def run(self):
        myThread = Thread(target=self.transmit)
        myThread.start()

    def transmit(self):
        while not self.endTransmission:
            self.screen.updateScreen(f"Sending:\n{self.activeMessage}")
            wordList = self.activeMessage.split()
            lenWords = len(wordList)
            wordsCounter = 1

            for word in wordList:
                lenWord = len(word)
                wordCounter = 1

                for char in word:
                    morse = self.morseDict.get(char.upper())
                    if morse is None:
                        continue

                    lenMorse = len(morse)
                    morseCounter = 1

                    for x in morse:
                        if self.current_state.id == "off":
                            if x == '.':
                                self.doDot()
                            elif x == '-':
                                self.doDash()

                        if morseCounter < lenMorse and self.current_state.id == "off":
                            self.doDDP()
                        morseCounter += 1

                    if wordCounter < lenWord and self.current_state.id == "off":
                        self.doLP()
                    wordCounter += 1

                if wordsCounter < lenWords and self.current_state.id == "off":
                    self.doWP()
                wordsCounter += 1

        self.screen.cleanupDisplay()


cwMachine = CWMachine()
cwMachine.run()

greenButton = Button(24)
greenButton.when_pressed = cwMachine.processButton

repeat = True
while repeat:
    try:
        if DEBUG:
            print("Killing time in a loop...")
        sleep(20)
    except KeyboardInterrupt:
        print("Cleaning up. Exiting...")
        repeat = False
        cwMachine.endTransmission = True
        sleep(1)

