"""Run with python tests/test_search.py (standard library only)."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "main.py"


class Robot:
    def __init__(self):
        self.ms = 0
        self.heading = 350
        self.mask = 31
        self.echo = 5800
        self.buttons = {}
        self.wheels = [(0, 0)] * 4
        self.servos = []
        self.icon = None
        self.tick = lambda delay: None
        self.env = dict(
            number=float, DigitalPin=NS(**{f"P{i}": i for i in range(17)}),
            MotionBitMotorChannel=NS(ALL=0, M1=1, M2=2, M3=3, M4=4),
            MotionBitMotorDirection=NS(FORWARD=1, BACKWARD=-1),
            MotionBitServoChannel=NS(S1=1, S2=2, S4=4, S5=5),
            Button=NS(A="A", B="B"), IconNames=NS(YES=1, NO=0),
            input=NS(on_button_pressed=self.buttons.__setitem__, running_time=lambda: self.ms,
                     compass_heading=lambda: self.heading),
            PulseValue=NS(HIGH=1), NumberFormat=NS(UINT8_LE=0),
            pins=NS(digital_read_pin=lambda p: (self.mask >> (p - 12)) & 1,
                    digital_write_pin=self.trig, pulse_in=self.pulse,
                    i2c_write_number=lambda *args: None, i2c_read_number=lambda *args: 0),
            motionbit=NS(run_motor=self.drive, brake_motor=self.brake, set_servo_position=self.servo),
            basic=NS(pause=self.pause, clear_screen=lambda: None, show_string=lambda text: None,
                     show_icon=lambda icon: setattr(self, "icon", icon)),
            control=NS(wait_micros=lambda delay: None),
        )
        exec(compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec"), self.env)

    def trig(self, pin, value):
        assert pin == 0

    def pulse(self, pin, level, timeout):
        assert pin == 1
        return self.echo

    def drive(self, motor, direction, speed):
        assert 175 <= speed <= 255
        if motor == 0:
            assert speed == 255
            self.wheels[:] = [(direction, speed)] * 4
        else:
            self.wheels[motor - 1] = (direction, speed)

    def brake(self, channel):
        self.wheels[:] = [(0, 0)] * 4

    def servo(self, pin, angle):
        assert self.wheels == [(0, 0)] * 4
        self.servos.append((pin, angle))

    def pause(self, delay):
        self.ms += delay
        assert self.ms < 30000, "route did not finish"
        assert self.wheels[0] == self.wheels[1] and self.wheels[2] == self.wheels[3]
        self.tick(delay)


class SearchTest(unittest.TestCase):
    def test_search_and_grip(self):
        for drift, turn_step in [(15, 15), (-15, 15), (15, 16)]:
            with self.subTest(drift=drift, turn_step=turn_step):
                robot = Robot()
                self.assertEqual((robot.icon, robot.ms, robot.servos),
                                 (1, 1000, [(2, 90), (4, 10), (5, 20)]))
                reverse_times, turns = [], []
                straight_ms = progress = previous_trim = 0
                drifted = corrected = False

                def tick(delay):
                    nonlocal straight_ms, progress, previous_trim, drifted, corrected
                    (left, power_l), (right, power_r) = robot.wheels[::2]
                    if left == right == 1:
                        straight_ms += delay
                        trim = power_l - power_r
                        self.assertEqual(max(power_l, power_r), 255)
                        self.assertLessEqual(abs(trim - previous_trim), 16)
                        previous_trim = trim
                        if not drifted:
                            self.assertEqual(trim, 0)
                            robot.heading = (350 + drift) % 360
                            drifted = True
                        elif not corrected and trim:
                            self.assertLess(trim * drift, 0)
                            robot.heading = 350
                            corrected = True
                        if len(turns) < 2 and straight_ms >= (325 if turns else 9000):
                            robot.mask = 0
                        elif len(turns) == 2 and straight_ms >= 325:
                            robot.echo = 580
                    elif left == right == -1:
                        self.assertEqual((robot.mask, power_l, power_r), (0, 255, 255))
                        reverse_times.append(delay)
                        progress = straight_ms = previous_trim = 0
                    elif (left, right) == (1, -1):
                        self.assertEqual((power_l, power_r), (255, 255))
                        robot.heading = (robot.heading + turn_step) % 360
                        progress += turn_step
                        if progress >= 86:
                            turns.append(robot.heading)
                            robot.mask = 31
                    elif robot.mask == 0 and progress:
                        self.fail("stopped mid-turn")

                robot.tick = tick
                robot.buttons["A"]()
                self.assertTrue(corrected)
                self.assertEqual(reverse_times, [50, 50])
                self.assertEqual(turns, [80, 170] if turn_step == 15 else [86, 182])
                self.assertEqual(robot.servos[3:], [(4, 10), (5, 20)] * 2)
                self.assertEqual(robot.icon, 1)

    def test_alignment(self):
        cases = [(31 ^ (1 << i), 1 if i <= 2 else -1, "recover") for i in range(5)]
        for mask, direction, action in cases + [(0, -1, "turn"), (28, 1, "timeout"), (28, 1, "cancel")]:
            with self.subTest(mask=mask, action=action):
                robot = Robot()
                robot.mask = mask
                aligned = False

                def tick(delay):
                    nonlocal aligned
                    left, right = (wheel[0] for wheel in robot.wheels[::2])
                    if left == 0:
                        return
                    if robot.mask == 0:
                        if (left, right) == (1, -1):
                            robot.mask = 7
                    elif robot.mask != 31:
                        self.assertEqual((left, right), (direction, -direction))
                        aligned = True
                        if action == "cancel":
                            robot.buttons["B"]()
                        elif action != "timeout":
                            robot.mask = 31
                    else:
                        self.assertEqual((left, right), (1, 1))
                        robot.echo = 580

                robot.tick = tick
                robot.buttons["A"]()
                self.assertTrue(aligned)
                self.assertEqual(robot.icon, int(action in ("recover", "turn")))
                self.assertEqual(robot.wheels, [(0, 0)] * 4)

    def test_cancel_while_reversing(self):
        robot = Robot()
        robot.mask = 0
        robot.tick = lambda delay: robot.buttons["B"]() if robot.wheels[0][0] == -1 else None
        robot.buttons["A"]()
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        self.assertEqual(robot.servos[-2:], [(1, 90), (2, 90)])
        self.assertEqual(robot.icon, 0)


if __name__ == "__main__":
    unittest.main()
