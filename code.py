# Network Studio Clock
# Runs on MatrixPortal M4.

# Based on Adafruit Metro Matrix Clock
# For Airlift Metro M4 with 64x32 RGB Matrix display & shield

# Copyright (c) 2018 Adafruit Industries
# Copyright (C) 2021 Raphaël Doursenaud <rdoursenaud@free.fr>

# Adapted to MatrixPortal M4.
# Defaults to using standard NTP instead of adafruit.io to fetch time.
# Added a 24 hours display mode.
# Added seconds display.
# Added Gorgy Timing inspired seconds chaser
# Added date display.
# Added button handling for stealth mode.


# TODO:
# - [ ] USB-MIDI support
# - [ ] MIDI Time Code (MTC) display
# - [ ] HUI mode
#   - [ ] timecode
#   - [ ] bargraph
# - [ ] MCU mode (See https://github.com/EMATech/PythonMcu)
#   - [ ] timecode
#   - [ ] bargraph

import time
import board
import digitalio
import displayio
import terminalio
from adafruit_debouncer import Debouncer
from adafruit_display_text.label import Label
#from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from digitalio import DigitalInOut


UPDATEINTERVAL = 60 * 15  # Retrieve time from the Internet every [n] seconds
USENTP = True  # Uses adafruit.io otherwise
BLINK = True
TWENTYFOURHOURS = True
SHOWSECONDS = False
DEBUG = False

spi = None
esp = None

# --- Setup buttons ---
up_pin = DigitalInOut(board.BUTTON_UP)
up_pin.direction = digitalio.Direction.INPUT
up_pin.pull = digitalio.Pull.UP
up = Debouncer(up_pin)

down_pin = DigitalInOut(board.BUTTON_DOWN)
down_pin.direction = digitalio.Direction.INPUT
down_pin.pull = digitalio.Pull.UP
down = Debouncer(down_pin)

# --- ESP32 init for NTP ---
if USENTP:
    import busio
    from adafruit_esp32spi import adafruit_esp32spi
    from adafruit_ntp import NTP

    # If you are using a board with pre-defined ESP32 Pins:
    esp32_cs = DigitalInOut(board.ESP_CS)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)

    # If you have an externally connected ESP32:
    # esp32_cs = DigitalInOut(board.D9)
    # esp32_ready = DigitalInOut(board.D10)
    # esp32_reset = DigitalInOut(board.D5)

    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    ntp = NTP(esp)  # Initialize the NTP object

# Get wifi details and more from a secrets.py file
# FIXME: encrypt secrets
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise
print("    Metro Minimal Clock")
print("Time will be set for {}".format(secrets["timezone"]))

# --- Drawing setup ---
group = displayio.Group(max_size=4)  # Create a Group
bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object,width, height, bit depth
color = displayio.Palette(2)  # Create a color palette
color[0] = 0x000000  # black background
color[1] = 0xFF0000  # red
#color[2] = 0xCC4000  # amber
#color[3] = 0x85FF00  # greenish

# Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
group.append(tile_grid)  # Add the TileGrid to the Group

# --- Display setup ---
matrix = Matrix()
display = matrix.display
display.show(group)
# FIXME: Not implemented upstream. Only 0.0 is supported. All other values are treated as 1.0.
# display.brightness = 0.5
network = Network(
    status_neopixel=board.NEOPIXEL,
    esp=esp,
    external_spi=spi,
    debug=DEBUG,
)

font = terminalio.FONT
# if not DEBUG:
#    font = bitmap_font.load_font("/IBMPlexMono-Medium-24_jep.bdf")

date_label = Label(font)
clock_label = Label(font)

date_label.color = color[1]

# Seconds ticks
for x in range(2, 62, 5):
    bitmap[x, 0] = 1
    bitmap[x, 31] = 1


def update_display(*, hours=None, minutes=None, seconds=None, updating=False):
    hint = None
    now = time.localtime()  # Get the time values we need
    if DEBUG:
        print(now)

    if hours is None:
        hours = now[3]
    if hours >= 18 or hours < 6:  # evening hours to morning
        clock_label.color = color[1]
    elif hours >= 13:
        clock_label.color = color[1]  # afternoon
    else:
        clock_label.color = color[1]  # morning
    if not TWENTYFOURHOURS:
        hint = "AM"
        if hours > 12:  # Handle times later than 12:59
            hours -= 12
            hint = "PM"
        elif not hours:  # Handle times between 0:00 and 0:59
            hours = 12

    if minutes is None:
        minutes = now[4]
    if seconds is None:
        seconds = now[5]

    if BLINK:
        # FIXME: blink every 500 ms
        colon = ":" if seconds % 2 else " "
    else:
        colon = ":"
    if updating:
        colon = "."
    datefs = "{year}-{month:02d}-{day:02d}"
    date_label.text = datefs.format(year=now[0], month=now[1], day=now[2])
    bbx, bby, bbwidth, bbh = date_label.bounding_box
    # Center the date label
    date_label.x = round(display.width / 2 - bbwidth / 2)
    date_label.y = display.height // 4 + 1
    if DEBUG:
        print("Date Label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("Date Label x: {} y: {}".format(date_label.x, date_label.y))

    if TWENTYFOURHOURS:
        fs = "{hours:02d}{colon}{minutes:02d}"
    else:
        fs = "{hours}{colon}{minutes:02d}{hint}"
    if SHOWSECONDS and not updating:
        fs += "{colon}{seconds:02d}"
    clock_label.text = fs.format(
        hours=hours, minutes=minutes, seconds=seconds, colon=colon, hint=hint
    )
    bbx, bby, bbwidth, bbh = clock_label.bounding_box
    # Center the clock label
    clock_label.x = round(display.width / 2 - bbwidth / 2)
    clock_label.y = display.height // 4 * 3 - 3
    if DEBUG:
        print("Clock Label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("Clock Label x: {} y: {}".format(clock_label.x, clock_label.y))
    # Seconds chase
    if not updating:
        for x in range(seconds + 2, 62):
            bitmap[x + 1, 2] = 0
            bitmap[x, 29] = 1
        for x in range(2, seconds + 3):
            bitmap[x, 2] = 1  # Tick
            bitmap[x - 1, 29] = 0  # Inverse Tick
        if DEBUG:
            print(seconds)


last_check = None
update_display()  # Display whatever time is on the board
group.append(date_label)
group.append(clock_label)  # add the clock label to the group

while True:
    if last_check is None or time.monotonic() > last_check + UPDATEINTERVAL:
        try:
            update_display(updating=True)  # Make sure a colon is displayed while updating
            if not USENTP:
                network.get_local_time()  # Synchronize Board's clock to Internet
            else:
                if not network._wifi.is_connected:
                    network.connect()
                while not ntp.valid_time:
                    # TODO: handle DST and local time
                    ntp.set_time(
                        tz_offset=3600 * 2
                    )  # Fetch and set the microcontroller's current UTC time
                    print("Failed to obtain time, retrying in 5 seconds...")
                    time.sleep(5)
            last_check = time.monotonic()
        except RuntimeError as e:
            print("Some error occured, retrying! -", e)

    update_display()

    # Buttons Handling
    up.update()
    down.update()

    if up.fell:
        print("UP")
        display.brightness = 1.0
    if down.fell:
        print("DOWN")
        display.brightness = 0.0
    if DEBUG:
        print(display.brightness)

    # Moderate messages rate
    if DEBUG:
        time.sleep(1)
