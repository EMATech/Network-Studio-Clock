# Network Studio Clock

Adafruit MatrixPortal M4 and CircuitPython powered prototype.

Based upon Adafruit's
[Metro Matrix Clock](https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/code-the-matrix-clock)
for Airlift Metro M4 with 64x32 RGB Matrix display & shield.

Copyright (c) 2018 Adafruit Industries  
Copyright (c) 2021-2022 Raphaël Doursenaud <rdoursenaud@free.fr>

Licensed under MIT. See [LICENSE](LICENSE).

## Demonstration

[![YouTube playlist](https://img.youtube.com/vi/ypubVenMepg/0.jpg)](https://www.youtube.com/watch?v=ypubVenMepg&list=PLO_8VBdDOlzUNaUxs-q3nOqT12Y1sIdo9&index=1)

## BOM

- [Adafruit Matrix Portal Starter Kit - ADABOX 016 Essentials
  (PRODUCT ID: 4812)](https://www.adafruit.com/product/4812)  
  Contains:
    - [Adafruit Matrix Portal - CircuitPython Powered Internet Display
      (Product ID: 4745)](https://www.adafruit.com/product/4745)
    - [64x32 RGB LED Matrix - 4mm pitch
      (Product ID: 2278)](https://www.adafruit.com/product/2278)
    - [Black LED Diffusion Acrylic Panel - 10.2" x 5.1" - 0.1" / 2.6mm thick
      (Product ID: 4749)](https://www.adafruit.com/product/4749)
    - [Clear Adhesive Squares - 6 pack - UGlu Dashes
      (Product ID: 4813)](https://www.adafruit.com/product/4813)
    - [5V 2.5A Switching Power Supply with 20AWG MicroUSB Cable
      (Product ID: 1995)](https://www.adafruit.com/product/1995)
    - [Micro B USB to USB C Adapter
      (Product ID: 4299)](https://www.adafruit.com/product/4299)
- [Adafruit DS3231 Precision RTC - STEMMA QT
  (PRODUCT ID: 5188)](https://www.adafruit.com/product/5188)
- [STEMMA QT / Qwiic JST SH 4-Pin Cable - 50mm Long
  (PRODUCT ID: 4399)](https://www.adafruit.com/product/4399)

## How to use

1. Firmware updates
    1. Update the
       [ESP32 firmware](https://learn.adafruit.com/upgrading-esp32-firmware/upgrade-all-in-one-esp32-airlift-firmware).
    2. Update the
       [U2F Bootloader](https://circuitpython.org/board/matrixportal_m4).
    3. Install or update to
       [CircuitPython](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython) version 7.x.
2. Libraries
    1. Install the requirements listed in
       [`requirements-circuitpython.txt`](requirements-circuitpython.txt)
       on your Matrix Portal.
       (I tend to use [CircUp](https://circup.readthedocs.io/en/latest/)).
3. WLAN configuration
    1. Complete your informations into [`_secrets.py`](src/_secrets.py).
    2. Rename `_secrets.py` to `secrets.py`.
4. Installation
    1. Copy all the files under [`src`](src) to the root of your Matrix Portal storage.

## Features & TODO

- [x] Clock
    - [x] RTC
        - [x] Integrated into MCU
        - [x] DS3231
    - [x] NTP (WiFi)
    - [ ] GPS
- [x] USB-MIDI support (adafruit_midi)
- [x] MIDI Time Code (MTC) display
  (uses heavily modified snippets from Jeff Mikels'
  [timecode_tools](https://github.com/jeffmikels/timecode_tools))
    - [x] Adafruit MIDI MTC Quarter Frame support
    - [x] MTC decoding with correct frame sync
    - [ ] Performance optimization
- [ ] Transport status display
    - [ ] MTC
        - [x] running
        - [x] synced
        - [x] stopped
        - [ ] direction
        - [ ] FPS
    - [x] MTC synced
    - [ ] MIDI clock
        - [ ] Metronome display?
- [ ] HUI mode
    - [ ] timecode
    - [ ] bargraph
    - [ ] rec enable?
- [ ] MCU mode (See https://github.com/EMATech/PythonMcu)
    - [ ] timecode
    - [ ] bargraph
    - [ ] rec enable?
- [ ] Environmental sensors support?

## CHANGES from the Metro Matrix Clock

- Adapted to MatrixPortal M4.
- Defaults to using standard NTP instead of adafruit.io to fetch time.
- Added a 24 hours display mode.
- Added seconds display.
- Added [Gorgy Timing](https://www.gorgy-timing.fr) inspired seconds chaser and font.
- Added date display.
- Added button handling for stealth mode.
- Added RTC (DS3231) support.
- Added a prototype MIDI Time Code (MTC) display mode.

## Similar software programs

- https://github.com/orchetect/MIDIKitSync (Implementation looks to be on point)
- https://github.com/AlexDWong/MTCDisplay (Similar hardware)

