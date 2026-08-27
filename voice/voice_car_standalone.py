#!/usr/bin/env python3
"""CI1302 + Raspberry Pi + four-channel TB6612 voice car control.

No ROS 2, Speech_Lib, or Rosmaster_Lib is required.
"""

from __future__ import annotations

import signal
import sys
import time
from dataclasses import dataclass

import serial
from gpiozero import Motor


SERIAL_PORT = "/dev/myspeech"
SERIAL_BAUD = 115200

# Movement tuning. Start conservatively with the wheels raised off the floor.
DRIVE_SPEED = 0.30
TURN_SPEED = 0.28
DRIVE_SECONDS = 2.0
TURN_SECONDS = 0.55

# Change an item to True if that wheel rotates in the wrong physical direction.
INVERT = {
    "front_left": False,
    "front_right": True,
    "rear_left": False,
    "rear_right": True,
}

# CI1302 IDs from the supplied command table.
CMD_STOP = {0x00, 0x01, 0x02, 0x03}
CMD_FORWARD = 0x04
CMD_BACKWARD = 0x05
CMD_LEFT = 0x06
CMD_RIGHT = 0x07
CMD_SPIN_LEFT = 0x08
CMD_SPIN_RIGHT = 0x09


@dataclass(frozen=True)
class Frame:
    function_id: int
    command_id: int


class CI1302:
    HEADER = b"\xAA\x55"
    TAIL = 0xFB
    FRAME_SIZE = 5

    def __init__(self, port: str, baud: int) -> None:
        self.serial = serial.Serial(port, baud, timeout=0.02)
        self.buffer = bytearray()

    def read_frames(self) -> list[Frame]:
        waiting = self.serial.in_waiting
        chunk = self.serial.read(waiting if waiting else 1)
        if chunk:
            self.buffer.extend(chunk)

        frames: list[Frame] = []
        while True:
            start = self.buffer.find(self.HEADER)
            if start < 0:
                # Preserve a possible first header byte at a chunk boundary.
                if self.buffer.endswith(b"\xAA"):
                    self.buffer[:] = b"\xAA"
                else:
                    self.buffer.clear()
                break

            if start:
                del self.buffer[:start]

            if len(self.buffer) < self.FRAME_SIZE:
                break

            candidate = self.buffer[: self.FRAME_SIZE]
            if candidate[4] != self.TAIL:
                del self.buffer[0]
                continue

            frames.append(Frame(candidate[2], candidate[3]))
            del self.buffer[: self.FRAME_SIZE]

        return frames

    def speak_command_reply(self, command_id: int) -> None:
        # Replays the fixed response associated with a command in CI1302 firmware.
        self.serial.write(bytes((0xAA, 0x55, 0xFF, command_id, 0xFB)))

    def close(self) -> None:
        self.serial.close()


class Wheel:
    def __init__(self, in1: int, in2: int, pwm: int, inverted: bool) -> None:
        self.motor = Motor(
            forward=in1,
            backward=in2,
            enable=pwm,
            pwm=True,
        )
        self.inverted = inverted

    def set(self, value: float) -> None:
        value = max(-1.0, min(1.0, value))
        if self.inverted:
            value = -value

        if value > 0:
            self.motor.forward(value)
        elif value < 0:
            self.motor.backward(-value)
        else:
            self.motor.stop()

    def close(self) -> None:
        self.motor.stop()
        self.motor.close()


class FourWheelChassis:
    def __init__(self) -> None:
        # BCM GPIO numbers from the supplied TB6612 board pin table.
        self.front_left = Wheel(17, 27, 25, INVERT["front_left"])
        self.front_right = Wheel(22, 23, 24, INVERT["front_right"])
        self.rear_left = Wheel(5, 6, 12, INVERT["rear_left"])
        self.rear_right = Wheel(13, 19, 18, INVERT["rear_right"])
        self.wheels = (
            self.front_left,
            self.front_right,
            self.rear_left,
            self.rear_right,
        )

    def drive(self, left: float, right: float) -> None:
        self.front_left.set(left)
        self.rear_left.set(left)
        self.front_right.set(right)
        self.rear_right.set(right)

    def stop(self) -> None:
        self.drive(0.0, 0.0)

    def close(self) -> None:
        for wheel in self.wheels:
            wheel.close()


def main() -> int:
    chassis = FourWheelChassis()
    speech: CI1302 | None = None
    stop_at: float | None = None
    running = True

    def request_exit(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, request_exit)
    signal.signal(signal.SIGTERM, request_exit)

    try:
        chassis.stop()
        speech = CI1302(SERIAL_PORT, SERIAL_BAUD)
        print(f"CI1302 connected: {SERIAL_PORT} @ {SERIAL_BAUD}")
        print("Commands: forward, backward, left, right, stop")

        while running:
            for frame in speech.read_frames():
                print(
                    f"frame function=0x{frame.function_id:02X} "
                    f"command=0x{frame.command_id:02X}"
                )

                # Motion commands are function type 0x00 in the supplied firmware.
                if frame.function_id != 0x00:
                    continue

                command = frame.command_id
                now = time.monotonic()

                if command in CMD_STOP:
                    chassis.stop()
                    stop_at = None
                    print("STOP")
                elif command == CMD_FORWARD:
                    chassis.drive(DRIVE_SPEED, DRIVE_SPEED)
                    stop_at = now + DRIVE_SECONDS
                    print("FORWARD")
                elif command == CMD_BACKWARD:
                    chassis.drive(-DRIVE_SPEED, -DRIVE_SPEED)
                    stop_at = now + DRIVE_SECONDS
                    print("BACKWARD")
                elif command in (CMD_LEFT, CMD_SPIN_LEFT):
                    chassis.drive(-TURN_SPEED, TURN_SPEED)
                    stop_at = now + TURN_SECONDS
                    print("LEFT")
                elif command in (CMD_RIGHT, CMD_SPIN_RIGHT):
                    chassis.drive(TURN_SPEED, -TURN_SPEED)
                    stop_at = now + TURN_SECONDS
                    print("RIGHT")
                else:
                    continue

                speech.speak_command_reply(command)

            if stop_at is not None and time.monotonic() >= stop_at:
                chassis.stop()
                stop_at = None
                print("AUTO STOP")

            time.sleep(0.01)

        return 0
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1
    finally:
        chassis.stop()
        chassis.close()
        if speech is not None:
            speech.close()
        print("Motors stopped; program exited")


if __name__ == "__main__":
    raise SystemExit(main())
