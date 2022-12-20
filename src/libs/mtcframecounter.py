# SPDX-FileCopyrightText: 2021-2022 Raphaël Doursenaud <rdoursenaud@free.fr>
# SPDX-License-Identifier: MIT
import time

import adafruit_midi
from adafruit_midi.mtc_quarter_frame import MtcQuarterFrame
from adafruit_midi.system_exclusive import SystemExclusive


# class Direction(IntEnum):
#    UNKNOWN = 0
#    FORWARD = 1
#    BACKWARD = -1

# Profiling
def timed_function(f, *args, **kwargs):
    myname = str(f).split(' ')[1]

    def new_func(*args, **kwargs):
        t = time.monotonic_ns()
        result = f(*args, **kwargs)
        delta = time.monotonic_ns() - t
        print('Function {} Time = {:6.3f}ms'.format(myname, delta / 1000))
        return result

    return new_func


class MTCFrameCounter:
    """
    An SMPTE MTC frame counter compliant with the official MIDI specifications:
    - MMA0001
    - RP004
    - RP008
    - MIDI 1.0 Detailed Specification v 4.1.1 and the MIDI 1.0 Addendum v 4.2

    https://www.midi.org
    """

    # TODO:
    # - [x] lock on quarter frame
    #   - [x] One full accumulator 8 to 16 full messages
    #         depending on where the sequence starts (message_type = 7)
    # - [x] Running first QF after full frame
    # - [x] detect direction
    #   - [x] Display direction (tri-state backward: "<", forward: ">" or unknown: "·")
    # - [x] Extract FPS
    #   - [x] Display FPS
    # - [x] update display for every frame at 0 and 4 QF
    #       (Respectively +-2 or +-3 frame depending on the direction)
    # - [ ] unlock/unrun on NAK (SysEx F0 7E <device ID> 7E pp F7 with pp == packet number)
    # - [ ] Decode SMPTE user bits?
    # - [ ] Decode MIDI Cueing messages?
    # - [ ] Write tests!!!

    RUNNING_TIMEOUT = 1 * 1e9  # 1 second

    @property
    def frame(self) -> int:
        return self._frame

    @frame.setter
    #    @timed_function
    def frame(self, value: int) -> None:
        # FIXME: duplicated code. Use a Timecode object instead?
        framerate_int = int(round(self.framerate))  # FIXME: Naive. Probably only works with NDF. Use TimeCode lib!
        if value < 0:  # Underflow
            value += framerate_int
            self.second -= 1
            if self.second < 0:
                self.second += 60
                self.minute -= 1
            if self.minute < 0:
                self.minute += 60
                self.hour -= 1
            if self.hour < 0:
                self.hour += 24
        if value > framerate_int:  # Overflow
            value -= framerate_int
            self.second += 1
            if self.second > 60:
                self.second -= 60
                self.minute += 1
            if self.minute > 60:
                self.minute -= 60
                self.hour += 1
            if self.hour > 24:
                self.hour -= 24
        self._frame = value

    @property
    def direction(self) -> int:
        return self._direction

    @direction.setter
    def direction(self, value: int) -> None:
        self._uf = 0  # Reset uncountable frames
        self._rst_qf_acc()
        self._direction = value

    @property
    def timecode(self) -> str:
        """
        Formats human readable timecode
        """
        return f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}:{self.frame:02d}"

    @property
    def timedout(self) -> bool:
        """
        Checks if we recently received MTC messages
        """
        timed_out = False

        now = time.monotonic_ns()
        prev_msg_ts = self._prev_msg_ts

        if now > (prev_msg_ts + self.RUNNING_TIMEOUT):
            self.locked = False
            self.running = False

        if now > (prev_msg_ts + self._timeout):
            # Update state
            self.direction = 0  # Direction.UNKNOWN
            self.locked = False
            self.running = False
            timed_out = True

        return timed_out

    def __init__(self, timeout=30) -> None:
        # Internal timecode counter
        # TODO: move to a TimeCode object?
        self.hour: int = 0
        self.minute: int = 0
        self.second: int = 0
        self._frame: int = 0

        # Uncountable frames.
        # Used while the direction is still unknown.
        self._uf: int = 0

        # Metadata
        self.framerate: float = 0.0

        self._direction: int = 0  # Direction.UNKNOWN

        # Allows detecting direction
        self._prev_qf_type: None | int = None

        # Transport running state
        self.running: bool = False

        # Allows detecting running state
        self._rcv_ff: bool = False

        # Are we locked onto the MTC
        self.locked: bool = False

        # Quarter frame MTC messages accumulator.
        # Store up to 4 frames (16 quarter frames) worth of data to allow syncing.
        self._qf_acc: [None | int] = [
            None,  # Frame count LS nibble
            None,  # Frame count MS nibble
            None,  # Seconds count LS nibble
            None,  # Seconds count MS nibble
            None,  # Minutes count LS nibble
            None,  # Minutes count MS nibble
            None,  # Hours count LS nibble
            None,  # Hours count MS nibble and SMPTE Type
        ]

        # Timestamps
        self._prev_msg_ts: int = time.monotonic_ns()
        self._timeout: float = timeout * 1e9  # Converts secs to nanoseconds

    @staticmethod
    def _is_ff_msg(msg: SystemExclusive) -> bool:
        """
        Determines if a SysEx message contains MTC Full Frame
        """
        return len(msg.data) == 7 and msg.data[1:3] == b'\x01\x01'

    @staticmethod
    #    @timed_function
    def _dec_hrs(hrs: int) -> (int, int):
        """
        Decode MTC hours.

        Hours count: x yy zzzzz
        x: always 0 and receiver should ignore!
        yy: Time Code Type
        zzzzz: hours Count (0-23)
        """
        hrs = hrs & 0b01111111  # Always ignore first bit
        tc_type = hrs >> 5
        if tc_type not in range(4):
            raise ValueError("Invalid timecode type")
        hrs_cnt = hrs & 0b00011111
        if hrs_cnt not in range(0, 24):
            raise ValueError("Invalid hour count")

        framerate = [24, 25, 29.97, 30][tc_type]

        return framerate, hrs_cnt

    @staticmethod
    #    @timed_function
    def _dec_mins(mins: int) -> int:
        """
        Decode MTC minutes.

        Minutes count: xx yyyyyy
        xx: undefined and reserved for future use receiver should ignore!
        yyyyyy: mins count (0-59)
        """
        mins_cnt = mins & 0b00111111
        if mins_cnt not in range(0, 60):
            raise ValueError("Invalid minute count")

        return mins_cnt

    @staticmethod
    #    @timed_function
    def _dec_secs(secs: int) -> int:
        """
        Decode MTC seconds.

        Seconds count: xx yyyyy
        xx: undefined and reserved for future use receiver should ignore!
        yyyyyy: secs count (0-59)
        """
        secs_cnt = secs & 0b00111111
        if secs_cnt not in range(0, 60):
            raise ValueError("Invalid secs count")

        return secs_cnt

    @staticmethod
    #    @timed_function
    def _dec_frm(frame: int) -> int:
        """
        Decode MTC frames.

        Frame count: xxx yyyyy
        xxx: undefined and reserved for future use receiver should ignore!
        yyyyy: Frame count (0-29)
        """
        frm_cnt = frame & 0b00011111
        if frm_cnt not in range(0, 30):
            raise ValueError("Invalid frame count")

        return frm_cnt

    #    @timed_function
    def _rst_qf_acc(self) -> None:
        """
        Resets the Quarter Frame Accumulator to a known state.
        """
        self._qf_acc = [None] * 8

#     #    @timed_function
#     def _mtc_full(self, msg: SystemExclusive, ts: int) -> None:
#         """
#         Interprets MTC Full Messages
#         """
#         self._prev_msg_ts = ts
#
#         # Decode and populate counter
#         self.framerate, self.hour = self._dec_hrs(msg.data[3])
#         self.minute = self._dec_mins(msg.data[4])
#         self.second = self._dec_secs(msg.data[5])
#         self._frame = self._dec_frm(msg.data[6])
#
#         # Update state
#         self._rcv_ff = True
#         self._prev_qf_type = None
#         self.running = False
#         self.direction = 0  # Direction.UNKNOWN
#
# #    @timed_function
#     def _mtc_qf(self, msg: MtcQuarterFrame, ts: int) -> None:
#         """
#         Interprets MTC Quarter Frame Messages
#
#         FIXME: Time sensitive! We need to handle this in less than a 4th of 30th of a second (~8.33 ms)
#         """
#         self._prev_msg_ts = ts
#
#         # Time is considered running on first QF after FF
#         if self._rcv_ff and not self.running:
#             self._rcv_ff = False
#             self.running = True
#
#         # Detect direction
#         direction = 0
#         if self._prev_qf_type is not None:
#             direction = msg.type - self._prev_qf_type
#             direction = (1 if direction == -7 else direction)
#             direction = (-1 if direction == 7 else direction)
#             #print(f"Direction: {direction}")
#             if self.direction != direction:
#                 self.direction = direction
#         self._prev_qf_type = msg.type  # Allows detecting direction change
#
#         # Update count at frame boundaries (1st and 5th quarter frame)
#         if msg.type in (0, 4):
#             if direction is not 0:  # Direction.UNKNOWN
#                 self.frame += direction * (self._uf + 1)
#                 self._uf = 0  # Reset uncountable frames
#             else:
#                 self._uf += 1  # Store for later use
#
#         # Record received QF
#         self._qf_acc[msg.type] = msg.value
#
#         # Verify if we’re locked every 8-message sequences (2 frames)
#         if (
#                 direction == 1 and msg.type == 7  # Direction.FORWARD
#         ) or (
#                 direction == -1 and msg.type == 0  # Direction.BACKWARD
#         ):
#             self._qf_sync()
#
#     #    @timed_function
#     def _qf_sync(self) -> None:
#         """
#         Checks received Quarter Frame data against our Internal Counter and locks if good.
#         """
#         # We need a full set of 8 messages
#         if None in self._qf_acc:
#             self.locked = False
#         else:
#             # MTC Quarter Frame uses the same format as MTC Full messages
#             # They are received in the reverse order
#             fr = self._dec_frm(self._qf_acc[0] + self._qf_acc[1] * 16)
#             self.second = self._dec_secs(self._qf_acc[2] + self._qf_acc[3] * 16)
#             self.minute = self._dec_mins(self._qf_acc[4] + self._qf_acc[5] * 16)
#             self.framerate, self.hour = self._dec_hrs(self._qf_acc[6] + self._qf_acc[7] * 16)
#
#             # We need to account for a 2 frame offset following the direction
#             # before comparing since the first QF message is 2 frames old at this time (We received 8 of them).
#             self.frame = fr + 2
#
#             self.running = True
#             self.locked = True
#             self._rst_qf_acc()

    #    @timed_function
    def midi(self, msg: adafruit_midi.MIDIMessage, ts: int) -> (bool, bool):
        """
        Interprets MTC messages and feeds the counter.
        """
        is_mtc = False
        is_frame = False

        # Quarter frame
        if isinstance(msg, MtcQuarterFrame):
            # self._mtc_qf(msg, ts)

            # --- UNROLL TEST
            self._prev_msg_ts = ts

            # Time is considered running on first QF after FF
            if self._rcv_ff and not self.running:
                self._rcv_ff = False
                self.running = True

            # Detect direction
            direction = 0
            if self._prev_qf_type is not None:
                direction = msg.type - self._prev_qf_type
                if direction not in(-1, 1):
                    if direction == -7:
                        direction = 1
                    elif direction == 7:
                        direction = -1
                # print(f"Direction: {direction}")
                if self.direction != direction:
                    self.direction = direction
            self._prev_qf_type = msg.type  # Allows detecting direction change

            # Update count at frame boundaries (1st and 5th quarter frame)
            if msg.type in (0, 4):
                is_frame = True
                if direction is not 0:  # Direction.UNKNOWN
                    self.frame += direction * (self._uf + 1)
                    self._uf = 0  # Reset uncountable frames
                else:
                    self._uf += 1  # Store for later use

            # Record received QF
            self._qf_acc[msg.type] = msg.value

            # Verify if we’re locked every 8-message sequences (2 frames)
            if (
                    direction == 1 and msg.type == 7  # Direction.FORWARD
            ) or (
                    direction == -1 and msg.type == 0  # Direction.BACKWARD
            ):
                # We need a full set of 8 messages
                if None not in self._qf_acc:
                    # MTC Quarter Frame uses the same format as MTC Full messages
                    # They are received in the reverse order
                    fr = self._dec_frm(self._qf_acc[0] + self._qf_acc[1] * 16)
                    self.second = self._dec_secs(self._qf_acc[2] + self._qf_acc[3] * 16)
                    self.minute = self._dec_mins(self._qf_acc[4] + self._qf_acc[5] * 16)
                    self.framerate, self.hour = self._dec_hrs(self._qf_acc[6] + self._qf_acc[7] * 16)

                    # We need to account for a 2 frame offset following the direction
                    # before comparing since the first QF message is 2 frames old at this time (We received 8 of them).
                    self.frame = fr + 2

                    self.running = True
                    self.locked = True
                    self._rst_qf_acc()
            # ---

            is_mtc = True

        # Full frame
        elif isinstance(msg, SystemExclusive) and self._is_ff_msg(msg):
            #self._mtc_full(msg, ts)

            # --- UNROLL TEST
            self._prev_msg_ts = ts

            # Decode and populate counter
            self.framerate, self.hour = self._dec_hrs(msg.data[3])
            self.minute = self._dec_mins(msg.data[4])
            self.second = self._dec_secs(msg.data[5])
            self._frame = self._dec_frm(msg.data[6])

            # Update state
            self._rcv_ff = True
            self._prev_qf_type = None
            self.running = False
            self.direction = 0  # Direction.UNKNOWN
            # ---

            is_frame = True
            is_mtc = True

        # FIXME: NAK means synchronization is dropped

        # Not an MTC messages!
        #else:
        #    print(f"Not an MTC MIDI message: {repr(msg)}")

        return is_mtc, is_frame
