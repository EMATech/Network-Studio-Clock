# SPDX-FileCopyrightText: 2021-2022 Raphaël Doursenaud <rdoursenaud@free.fr>
# SPDX-License-Identifier: MIT

import gc

import board
import digitalio
import storage
import usb_hid
import usb_midi

DEBUG = True

USB_CDC = True
try:
    import usb_cdc
except ImportError:
    USB_CDC = False
    print("usb_cdc unavailable, skipping...")
    print("You may be running CircuitPython v6 and this feature requires v7.")

if USB_CDC:
    print("Enabling USB serial!")
    try:
        usb_cdc.enable()
    except AttributeError:
        print("Unable to enable USB serial!")

print("Disabling USB HID!")
try:
    usb_hid.disable()
except AttributeError:
    print("Unable to disable USB HID!")

print("Enabling USB MIDI!")
try:
    usb_midi.enable()
except AttributeError:
    print("Unable to enable USB MIDI!")

if not DEBUG:
    print("Press the DOWN button while powering up to run in DEBUG mode.")
else:
    print("Press the DOWN button while powering up to run in PRODUCTION mode.")

# Setup Button
button_down = digitalio.DigitalInOut(board.BUTTON_DOWN)
button_down.direction = digitalio.Direction.INPUT
button_down.pull = digitalio.Pull.UP
if button_down.value:
    DEBUG = not DEBUG

if not DEBUG:  # not button_down.value:
    print("Running in PRODUCTION mode!")

    print("Disabling USB drive!")
    try:
        storage.disable_usb_drive()
    except:
        print("storage.disable_usb_drive() unavailable, skipping...")
        print("You may be running CircuitPython v6 and this feature requires v7.")

    if USB_CDC:
        print("Disabling USB serial!")
        try:
            usb_cdc.disable()
        except AttributeError:
            print("Unable to disable USB CDC!")
else:
    print("Running in DEBUG mode!")

gc.collect()
