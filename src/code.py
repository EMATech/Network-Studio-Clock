# SPDX-FileCopyrightText: 2021-2022 Raphaël Doursenaud <rdoursenaud@free.fr>
# SPDX-License-Identifier: MIT

"""
Network Studio Clock

Runs on MatrixPortal M4.

# TODO
- [x] DS3231 RTC
- [ ] Use embedded accelerometer to reverse display
- [ ] Off/dim hours?

# FIXME
- [ ] Timezone/DST support (Using http://worldtimeapi.org ?)
"""

import gc
import math
import time

# import adafruit_requests as requests
import board
import digitalio
import displayio
import rtc
import supervisor
import usb_midi

import adafruit_ds3231
from adafruit_bitmap_font import bitmap_font
from adafruit_debouncer import Debouncer
from adafruit_display_text.label import Label
from adafruit_matrixportal.matrix import Matrix
from adafruit_matrixportal.network import Network
from adafruit_midi import MIDI
from adafruit_ntp import NTP
from mtcframecounter import MTCFrameCounter

DEBUG = False

gc.collect()
#if DEBUG:
#    print("DEBUG: free memory after imports", gc.mem_free())

# Get wifi details and more from a secrets.py file
# FIXME: encrypt secrets
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

#if DEBUG:
#    print("DEBUG: free memory after importing secrets", gc.mem_free())

# CONFIGURABLE SETTINGS ----------------------------------------------------

MODE = 'Clock'  # Preferred mode at bootup. Allowed values: 'Clock', 'MTC'.
TWENTYFOURHOURS = True
SHOWSECONDS = True
BLINK = True
SUMMER_TIME = False
TZ_OFFSET = 1  # Hours
USENTP = True  # Uses adafruit.io otherwise
UPDATEINTERVAL = 60 * 60 * 24  # Retrieve time from the Internet every [n] seconds
# CALIBRATION = -127  # FIXME: doesn’t work with microcontroller clock. Report
USB_MIDI_CHANNEL = 1  # 1-16
MTC_TIMEOUT = 30  # Seconds with no messages received to wait before switching to the clock

if SUMMER_TIME:
    TZ_OFFSET += 1

print("Studio Network Clock")


# GLOBALS -------------------------------------------------------------------


# FUNCTIONS -----------------------------------------------------------------


def second_ticks():
    # Seconds ticks
    # We have 64 pixels wide and we want to use the 60 in the center.
    # Let's move two pixels to the right!
    offset = 2
    for x in range(0, 60):
        clock_bitmap[x + offset, 30] = 1
    for x in range(0, 60, 5):
        clock_bitmap[x + offset, 1] = 1
        clock_bitmap[x + offset, 30] = 0


def display_clock(updating=False):
    hint = None
    # now = time.localtime()  # Get the time values we need
    now = rtc.RTC().datetime = hwrtc.datetime  # Get time from the hardware RTC
    # = now  # Update board RTC time to prevent it from drifting

    #if DEBUG:
    #    print(now)

    hours = now[3]

    time_label.color = color[1]
    # if hours >= 18 or hours < 6:
    #    time_label.color = color[1]  # evening hours to morning
    # elif hours >= 13:
    #    time_label.color = color[1]  # afternoon
    # else:
    #    time_label.color = color[1]  # morning

    if not TWENTYFOURHOURS:
        hint = "AM"
        if hours > 12:  # Handle times later than 12:59
            hours -= 12
            hint = "PM"
        elif not hours:  # Handle times between 0:00 and 0:59
            hours = 12

    minutes = now[4]

    seconds = now[5]

    if BLINK:
        # Blink every 500 ms
        # TODO: Rewrite using:
        #       https://circuitpython.readthedocs.io/en/latest/docs/library/uasyncio.html?
        colon = ":" if math.floor(supervisor.ticks_ms() / 500 % 2) else " "
    else:
        colon = ":"

    if updating:
        colon = "."

    date_fs = "{year}-{month:02d}-{day:02d}"  # ISO8601
    date_label.text = date_fs.format(year=now[0], month=now[1], day=now[2])

    if TWENTYFOURHOURS:
        time_fs = "{hours:02d}{colon}{minutes:02d}"
    else:
        time_fs = "{hint} {hours:02d}{colon}{minutes:02d}"

    if SHOWSECONDS and not updating:
        time_fs += "{colon}{seconds:02d}"

    time_label.text = time_fs.format(
        hours=hours, minutes=minutes, seconds=seconds, colon=colon, hint=hint
    )

    # Seconds chase
    if not updating:
        # We have 64 pixels wide and we want to use the 60 in the center.
        # Let's move two pixels to the right!
        offset = 2

        # FIXME: draw full
        if seconds == 0:
            for x_position in range(1, 60):
                clock_bitmap[x_position + offset, 2] = 0  # Blank ticks
                clock_bitmap[x_position + offset, 29] = 1  # Illuminate all Inverse ticks
        clock_bitmap[seconds + offset, 2] = 1  # Tick
        clock_bitmap[seconds + offset, 29] = 0  # Inverse tick blanking

        #if DEBUG:
        #    print(seconds)


def display_timecode(timecode="00:00:00:00"):
    #if DEBUG:
    #    print(timecode)

    tc_label.text = timecode


def update_display(
        *, timecode=None, updating=False
):
    # FIXME: factorize
    if timecode:
        #display_timecode(timecode)
        # --- Unroll TEST
        tc_label.text = timecode
        # ---
    else:
        display_clock(updating)


def update_time():
    if not USENTP:
        network.get_local_time()  # Synchronize Board's clock to Internet
    else:
        while not network._wifi.is_connected:
            network.connect()
            if not network._wifi.is_connected:
                # FIXME: Use exponential backoff
                #if DEBUG:
                #    print("Failed to connect to WiFi, retrying in 5 seconds...")
                time.sleep(5)
                continue
        time.sleep(1)  # Let network settle
        # esp.get_time()
        # while not ntp.valid_time:
        #     # TODO: handle DST and local time
        #     ntp.set_time(
        #         tz_offset=3600 * TZ_OFFSET
        #     )  # Fetch and set the microcontroller's current UTC time
        #     if not ntp.valid_time:
        #         # FIXME: Use exponential backoff
        #         if DEBUG:
        #             print("Failed to obtain time from NTP, retrying in 5 seconds...")
        #         time.sleep(5)
        #         continue
        # hwrtc.datetime = rtc.RTC().datetime  # Update the hardware real time clock module's time


# ONE-TIME INITIALIZATION --------------------------------------------------

gc.collect()
#if DEBUG:
#    print("DEBUG: free memory before init", gc.mem_free())

print("Initializing...")

# --- Display setup ---
matrix = Matrix(width=64, height=32)
display = matrix.display

# --- Drawing setup ---
color = displayio.Palette(4)  # Create a color palette
color[0] = 0x000000  # black background
# FIXME (upstream): anything below 40 is not visible!
#                   Brightness scaling could be better.
# FIXME (upstream): anything too bright is getting glitchy on the whole display.
color[1] = 0xFF0000  # red
color[2] = 0x888800  # yellow
color[3] = 0x00FF00  # green
# (Alternatives: 0x00FF88 [Hospital green], 0x404040 [Dim white], 0xFF4400 [Amber])

clock_bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object, width, height, bit depth
tc_bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object, width, height, bit depth

clock_tile_grid = displayio.TileGrid(clock_bitmap, pixel_shader=color)
tc_tile_grid = displayio.TileGrid(tc_bitmap, pixel_shader=color)

splash = displayio.Group()
clock_view = displayio.Group()
tc_view = displayio.Group()

clock_view.append(clock_tile_grid)
tc_view.append(tc_tile_grid)

if MODE == 'Clock':
    second_ticks()
    splash.append(clock_view)
else:
    splash.append(tc_view)

# FIXME: Not implemented upstream. Only 0.0 is supported.
#        All other values are treated as 1.0.
# display.brightness = 0.5

# Draw something ASAP
display.show(splash)

# Custom font
font = bitmap_font.load_font('/gt.pcf')
#if DEBUG:
#    font = bitmap_font.load_font('/gt.bdf')

date_label = Label(font)
date_label.color = color[1]
date_label.text = '0000-00-00'

# TODO: factorize
bbx, bby, bbwidth, bbh = date_label.bounding_box
date_x = display.width // 2 - bbwidth // 2
date_y = display.height // 4 + 2
date_label.x = date_x
date_label.y = date_y

time_label = Label(font)
time_label.color = color[1]
time_label.text = '00:00:00'

# TODO: factorize
bbx, bby, bbwidth, bbh = time_label.bounding_box
# FIXME: pre-compute to prevent flickering
time_x = display.width // 2 - bbwidth // 2
time_y = display.height // 4 * 3 - 1
time_label.x = time_x
time_label.y = time_y

tc_label = Label(font)
tc_label.color = color[1]
tc_label.text = '00:00:00:00'

# TODO: factorize
bbx, bby, bbwidth, bbh = tc_label.bounding_box
tc_label.x = round(display.width / 2 - bbwidth / 2)
tc_label.y = display.height // 2 - 1

clock_view.append(date_label)
clock_view.append(time_label)
tc_view.append(tc_label)

last_time_check = None

# --- Real Time Clock ---
print("Initializing hardware RTC (DS3231)")
hwrtc = adafruit_ds3231.DS3231(board.I2C())
#if DEBUG:
#    print(f"Hardware RTC temperature: {hwrtc.temperature}")
# rtc.set_time_source(hwrtc)
# r=rtc.RTC()

# Update clock display ASAP
display_clock()

# --- Setup buttons ---
up_pin = digitalio.DigitalInOut(board.BUTTON_UP)
up_pin.direction = digitalio.Direction.INPUT
up_pin.pull = digitalio.Pull.UP
up = Debouncer(up_pin)

down_pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
down_pin.direction = digitalio.Direction.INPUT
down_pin.pull = digitalio.Pull.UP
down = Debouncer(down_pin)

# --- USB MIDI ---
midi = MIDI(
    midi_in=usb_midi.ports[0],
    in_channel=USB_MIDI_CHANNEL - 1,
    midi_out=usb_midi.ports[1],
    out_channel=USB_MIDI_CHANNEL - 1,
)

# --- Networking ---
network = Network(debug=DEBUG)
esp = network._wifi.esp
#if DEBUG:
#    print(f"ESP32 co-processor running firmware v{esp.firmware_version.decode()}")
#    MAC_address = ''
#    for b in esp.MAC_address_actual:
#        MAC_address += '{:x}'.format(b)
#        MAC_address += ':'
#    MAC_address = MAC_address[:-1]  # Remove extraneous ':'
#    print(f"WiFi MAC Address: {MAC_address}")

if MODE == 'Clock':
    # FIXME: Handle wifi unavailable
    network.connect()
    #if DEBUG:
    #    print(f'WiFi signal strength: {esp.rssi}dB')
    #    print(f'Connected as {network.ip_address}')

if USENTP:
    ntp = NTP(esp)  # Initialize the NTP object

# Load time zone string from secrets.py, else IP geolocation for this too
# (http://worldtimeapi.org/api/timezone for list).
# try:
#    timezone = secrets['timezone']  # e.g. 'America/New_York'
# except (NameError, KeyError):
#    timezone = None

# Check timezone information
# if not timezone:
#    print("WARNING: no timezone information provided. Please update secrets.py.")

# else:
# print(f"DEBUG: timezone {timezone} declared")
# valid_tz = requests.get('http://worldtimeapi.org/api/timezone')
# if timezone not in valid_tz.json():
#    print(f"WARNING: {timezone} timezone is invalid. Please update secrets.py.")
#    valid_tz.close()

# else:
#    print("DEBUG: timezone valid, let’s get our offset!")
# Get UTC offset from WorldTimeAPI
#    tzinfo = requests.get(f"http://worldtimeapi.org/api/timezone/{timezone}")
#    TZ_OFFSET = tzinfo.json()['utc_offset']
#    print("DEBUG: offset set to: ", TZ_OFFSET)
#    tzinfo.close()

if MODE == 'Clock':
    # rtc.RTC().calibration = CALIBRATION
    # hwrtc.calibration = CALIBRATION
    update_time()
    last_time_check = supervisor.ticks_ms()

mtc_counter = MTCFrameCounter()

#if DEBUG:
#    print("DEBUG: free memory after init before GC", gc.mem_free())
gc.collect()
#if DEBUG:
#    print("DEBUG: free memory after GC", gc.mem_free())

# MAIN LOOP ----------------------------------------------------------------

print("Started!")

# SMPTE helpers
#prev_direction = 0
#prev_framerate = 0

while True:
    timestamp = time.monotonic_ns()

    is_mtc = False
    is_frame = False

    # MIDI
    message = midi.receive()

    if message:
        #if DEBUG:
        #    print("Received MIDI message")
        #    print(message)
        is_mtc, is_frame = mtc_counter.midi(message, timestamp)

    # Update caches
    #timecode = mtc_counter.timecode
    framerate = mtc_counter.framerate
    direction = mtc_counter.direction
    # running = mtc_counter.running
    # locked = mtc_counter.locked

    # Crude automatic mode switching
    if MODE == 'Clock' and is_mtc:
        #if DEBUG:
        #    print("Switching to MTC mode")
        # TODO: clear screen?
        MODE = 'MTC'
        splash.remove(clock_view)
        splash.append(tc_view)
    elif MODE == 'MTC' and mtc_counter.timedout:
        #if DEBUG:
        #    print("Switching to Clock mode")
        splash.remove(tc_view)
        splash.append(clock_view)
        second_ticks()
        # FIXME: second chase can be partially in sync
        MODE = 'Clock'

    if MODE == 'MTC':
        if mtc_counter.locked:
            tc_label.color = color[3]  # Green
        elif mtc_counter.running:
            tc_label.color = color[2]  # Yellow
        else:
            tc_label.color = color[1]  # Red

        if is_frame:
            #if DEBUG:
            #    print(f"MTC: {timecode}")
            #if prev_framerate != framerate:
                #if DEBUG:
                #    print(f"Frame Rate Change: {framerate}")
            #    prev_framerate = framerate

            #if prev_direction != direction:
            #    if direction == 1:
            #        dir_r = ">"
            #    elif direction == -1:
            #        dir_r = "<"
            #    else:
            #        dir_r = "-"
                #if DEBUG:
                #    print(f"Direction Change: {dir_r}")
            #    prev_direction = direction
            update_display(timecode=mtc_counter.timecode)

    elif MODE == 'Clock':
        # Time & display
        if last_time_check is None or timestamp > last_time_check + UPDATEINTERVAL * 1e9:
            # Make sure status is displayed while updating

            update_display(updating=True)
            try:
                update_time()
            except RuntimeError as e:
                print("Some error occurred, retrying! -", e)
            last_time_check = timestamp
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
    #if DEBUG:
    #    print("DEBUG: free memory", gc.mem_free())
    #   print(f"Main loop took: {time.monotonic_ns() - timestamp} ns")
