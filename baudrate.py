#!/usr/bin/env python3
# License:          MIT
# Authors:          
# Craig Heffner     @devttys0   https://github.com/devttys0
#                   @Loris1123  https://github.com/Loris1123
# Sick.Codes        @sickcodes  https://github.com/sickcodes
# Usage:
#           pip install -r requirements.txt
#           sudo python baudrate.py /dev/ttyUSB0

import subprocess
import sys
import termios
import time
import tty
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from getopt import GetoptError
from getopt import getopt as GetOpt
from threading import Thread

import getch
import serial


class RawInput:
    """Gets a single character from standard input.  Does not echo to the screen."""
    def __init__(self):
        try:
            self.impl = RawInputWindows()
        except ImportError:
            self.impl = RawInputUnix()

    def __call__(self): return self.impl()


class RawInputUnix:
    def __call__(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


class RawInputWindows:
    def __call__(self):
        return getch.getch()

class Baudrate:

    VERSION = '3.0'
    READ_TIMEOUT = 5
    BAUDRATES = [
        "110",
        "300",
        "600",
        "1200",
        "1800",
        "2400",
        "3600",
        "4800",
        "7200",
        "9600",
        "14400",
        "19200",
        "28800",
        "31250",
        "38400",
        "57600",
        "76800",
        "115200",
        "128000",
        "153600",
        "230400",
        "250000",
        "256000",
        "307200",
        "345600",
        "460800",
        "500000",
        "512000",
        "921600",
        "1024000",
        "2000000",
        "2500000",
        "3000000",
        "3686400",
    ]

    UPKEYS = ['u', 'U', 'A']
    DOWNKEYS = ['d', 'D', 'B']

    MIN_CHAR_COUNT = 25
    WHITESPACE = [' ', '\t', '\r', '\n']
    PUNCTUATION = ['.', ',', ':', ';', '?', '!']
    VOWELS = ['a', 'A', 'e', 'E', 'i', 'I', 'o', 'O', 'u', 'U']

    def __init__(self, port=None, threshold=MIN_CHAR_COUNT, timeout=READ_TIMEOUT, name=None, auto=True, verbose=False):
        self.port = port
        self.threshold = threshold
        self.timeout = timeout
        self.name = name
        self.auto_detect = auto
        self.verbose = verbose
        self.index = len(self.BAUDRATES) - 1
        self.valid_characters = []
        self.ctlc = False
        self.thread = None

        self._gen_char_list()

    def _gen_char_list(self):
        self.valid_characters = [chr(x) for x in range(ord("!"), ord("~")+1)]
        self.valid_characters.extend(self.WHITESPACE)

    def _print(self, data):
        if self.verbose:
            sys.stderr.buffer.write(data)
            sys.stderr.buffer.flush()

    def __enter__(self):
        self.Open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # ignore the exception info, let it bubble up
        self.Close()

    def Open(self):
        self.serial = serial.Serial(self.port, timeout=self.timeout)
        self.NextBaudrate(0)

    def NextBaudrate(self, updn):

        self.index += updn

        if self.index >= len(self.BAUDRATES):
            self.index = 0
        elif self.index < 0:
            self.index = len(self.BAUDRATES) - 1

        sys.stderr.write('\n\n@@@@@@@@@@@@@@@@@@@@@ Baudrate: %s @@@@@@@@@@@@@@@@@@@@@\n\n' % self.BAUDRATES[self.index])

        self.serial.flush()
        self.serial.baudrate = self.BAUDRATES[self.index]
        self.serial.flush()

    def Detect(self):
        count = 0
        whitespace = 0
        punctuation = 0
        vowels = 0
        start_time = 0
        timed_out = False
        clear_counters = False

        if not self.auto_detect:
            self.thread = Thread(None, self.HandleKeypress, None, (self, 1))
            self.thread.start()

        while True:
            if start_time == 0:
                start_time = time.time()

            byte = self.serial.read(1)

            if byte:
                if self.auto_detect and byte in self.valid_characters:
                    if byte in self.WHITESPACE:
                        whitespace += 1
                    elif byte in self.PUNCTUATION:
                        punctuation += 1
                    elif byte in self.VOWELS:
                        vowels += 1

                    count += 1
                else:
                    clear_counters = True

                self._print(byte)

                if count >= self.threshold and whitespace > 0 and punctuation > 0 and vowels > 0:
                    break
                elif (time.time() - start_time) >= self.timeout:
                    timed_out = True
            else:
                timed_out = True

            if timed_out and self.auto_detect:
                start_time = 0
                self.NextBaudrate(-1)
                clear_counters = True
                timed_out = False

            if clear_counters:
                whitespace = 0
                punctuation = 0
                vowels = 0
                count = 0
                clear_counters = False

            if self.ctlc:
                break

        return self.BAUDRATES[self.index]

    def HandleKeypress(self, *args):
        userinput = RawInput()
        while not self.ctlc:
            c = userinput()
            if c in self.UPKEYS:
                self.NextBaudrate(1)
            elif c in self.DOWNKEYS:
                self.NextBaudrate(-1)
            elif c == '\x03':
                self.ctlc = True

    def MinicomConfig(self, name=None):
        success = True

        if name is None:
            name = self.name

        config =  "########################################################################\n"
        config += "# Minicom configuration file - use \"minicom -s\" to change parameters.\n"
        config += "pu port             %s\n" % self.port
        config += "pu baudrate         %s\n" % self.BAUDRATES[self.index]
        config += "pu bits             8\n"
        config += "pu parity           N\n"
        config += "pu stopbits         1\n"
        config += "pu rtscts           No\n"
        config += "########################################################################\n"

        if name is not None and name:
            try:
                open("/etc/minicom/minirc.%s" % name, "w").write(config)
            except Exception as e:
                print("Error saving minicom config file:", str(e))
                success = False

        return (success, config)

    def Close(self):
        self.ctlc = True
        self.serial.close()

if __name__ == '__main__':

    def main():
        parser = ArgumentParser(
            formatter_class=RawDescriptionHelpFormatter,
            description=
            f"Baudrate v{Baudrate.VERSION}\n"
            "Craig Heffner, http://www.devttys0.com\n"
            "@Loris1123, https://github.com/Loris1123\n"
            "Sick.Codes, https://sick.codes\n"
        )
        parser.add_argument("-p", "--port", help="Specify the serial port to use", default="/dev/ttyUSB0")
        parser.add_argument("-t", "--timeout", help="Set the timeout period used when switching baudrates in auto detect mode", default=Baudrate.READ_TIMEOUT)
        parser.add_argument("-c", "--count", help="Set the minimum ASCII character threshold used during auto detect mode", default=Baudrate.MIN_CHAR_COUNT, type=int)
        parser.add_argument("-n", "--name", help="Save the resulting serial configuration as <name> and automatically invoke minicom (implies -a)", action="store")
        parser.add_argument("-a", "--auto", help="Enable auto detect mode", action="store_true")
        parser.add_argument("-b", "--baud-rates", help="Display supported baud rates and exit", action="store_true")
        parser.add_argument("-q", "--quiet", help="Do not display data read from the serial port", action="store_false")

        args = parser.parse_args()

        if args.baud_rates:
            print("Supported baud rates:")
            for rate in Baudrate.BAUDRATES:
                print(f"{rate}\n")
            print("")
            return

        port = args.port
        timeout = args.timeout
        threshold = args.count
        name = args.name
        auto = args.auto
        verbose = args.quiet
        run = False

        if name != None:
            run = True
            auto = True

        with Baudrate(port, threshold=threshold, timeout=timeout, name=name, verbose=verbose, auto=auto) as baud:
            print(f"\nStarting baudrate detection on {port}, turn on your serial device now.\n"
                "Press Up/Down to switch baud rates.\n"
                "Press Ctl+C to quit.\n")

            try:
                rate = baud.Detect()
                print(f"\nDetected baudrate: {rate}")

                if name is None:
                    print("\nSave minicom configuration as: ", end=" ")
                    name = sys.stdin.readline().strip()
                    print("")

                ok, config = baud.MinicomConfig(name)
                if name and name is not None and ok:
                    if not run:
                        print("Configuration saved. Run minicom now [n/Y]? ", end="")
                        yn = sys.stdin.readline().strip()
                        print("")
                        if yn == "" or yn.lower().startswith('y'):
                            run = True

                    if run:
                        subprocess.call(["minicom", name])
                else:
                    print(config)
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"Exception: {e}")

    main()

