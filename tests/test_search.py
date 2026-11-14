"""Run with python tests/test_search.py (standard library only)."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "main.py"


class Robot:
    def __init__(self, sensor_present=True):
        self.ms = 0
        self.heading = 350
        self.mask = 31
        self.echo = 5800
        self.buttons = {}
        self.wheels = [(0, 0)] * 4
        self.servos = []
        self.sensor_probes = 0
        self.icon = None
        self.tick = lambda delay: None
        self.pick_color = 1
        self.carry_steps = 0
        self.env = dict(
            number=float, DigitalPin=NS(**{f"P{i}": i for i in range(17)}),
            MotionBitMotorChannel=NS(ALL=0, M1=1, M2=2, M3=3, M4=4),
            MotionBitMotorDirection=NS(FORWARD=1, BACKWARD=-1),
            MotionBitServoChannel=NS(S1=1, S2=2, S3=3),
            Button=NS(A="A", B="B"), IconNames=NS(YES=1, NO=0),
            input=NS(on_button_pressed=self.buttons.__setitem__, running_time=lambda: self.ms,
                     compass_heading=lambda: self.heading),
            PulseValue=NS(HIGH=1), NumberFormat=NS(UINT8_LE=0),
            pins=NS(digital_read_pin=lambda p: (self.mask >> (p - 12)) & 1,
                    digital_write_pin=self.trig, pulse_in=self.pulse,
                    i2c_write_number=lambda *args: None, i2c_write_buffer=lambda *args: None,
                    i2c_read_number=lambda *args: self.chip_id(sensor_present)),
            motionbit=NS(run_motor=self.drive, brake_motor=self.brake, set_servo_position=self.servo),
            basic=NS(pause=self.pause, clear_screen=lambda: None, show_string=lambda text: None,
                     show_icon=lambda icon: setattr(self, "icon", icon)),
            control=NS(wait_micros=lambda delay: None), serial=NS(write_line=lambda text: None),
        )
        exec(compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec"), self.env)
        self.classify = self.env["floor_color"]
        self.env["floor_color"] = self.floor_color

    def chip_id(self, present):
        self.sensor_probes += 1
        return 0x44 if present else 0

    def floor_color(self):
        # Same pickup patch, wrong colour, then a separate matching patch.
        if self.env["carrying_color"] and 3 <= self.carry_steps < 7:
            return 1 if self.pick_color == 3 else 3
        return self.pick_color

    def trig(self, pin, value):
        assert pin == 0

    def pulse(self, pin, level, timeout):
        assert pin == 1
        assert not self.env["carrying_color"], "held can must not trigger pickup again"
        return self.echo

    def drive(self, motor, direction, speed):
        assert not self.env["stopped"], "wheel command after B"
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
        if self.env["carrying_color"] and self.wheels[0][0] == self.wheels[2][0] == 1:
            self.carry_steps += 1
        self.tick(delay)


class SearchTest(unittest.TestCase):
    def test_rgb_samples(self):
        robot = Robot()
        for sample, expected in [((150, 80, 72, 18), 4), ((150, 95, 30, 25), 1),
                                 ((150, 26, 88, 22), 3), ((150, 22, 35, 85), 2),
                                 ((150, 55, 55, 55), 0), ((0, 0, 0, 0), -1)]:
            with self.subTest(sample=sample):
                buf = NS(get_number=lambda fmt, offset: sample[offset // 2])
                robot.env["pins"].i2c_read_buffer = lambda addr, n: buf
                robot.env["NumberFormat"].UINT16_LE = 1
                self.assertEqual(robot.classify(), expected)

    def test_search_and_grip(self):
        for drift, turn_step in [(15, 15), (-15, 15), (15, 16)]:
            with self.subTest(drift=drift, turn_step=turn_step):
                robot = Robot()
                self.assertEqual((robot.icon, robot.ms, robot.servos),
                                 (1, 1065, [(2, 45), (3, 45)]))
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
                self.assertEqual(robot.servos[2:], [
                    (2, 45), (3, 45), (1, 75), (1, 90), (1, 105), (1, 90), (3, 45), (2, 45)])
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

    def test_delivers_each_color_only_at_a_separate_matching_patch(self):
        for color in (1, 2, 3, 4):
            with self.subTest(color=color):
                robot = Robot()
                robot.pick_color = color
                robot.echo = 580
                robot.env.update(GRIP_RIGHT_CLOSED=60, GRIP_LEFT_CLOSED=70,
                                 RACK_UP_MS=300, RACK_DOWN_MS=300)
                robot.buttons["A"]()
                self.assertGreaterEqual(robot.carry_steps, 7)
                self.assertEqual(robot.icon, 1)
                cycle = [(2, 70), (3, 60), (1, 75), (1, 90),
                         (1, 105), (1, 90), (3, 45), (2, 45)]
                self.assertEqual(robot.servos[2:], cycle)
                robot.carry_steps = 0
                robot.buttons["A"]()
                self.assertEqual(robot.icon, 1)
                self.assertEqual(robot.servos[2:], cycle * 2)
                self.assertEqual(robot.sensor_probes, 1)

    def test_cancel_during_pickup_lift_requires_reset(self):
        robot = Robot()
        robot.echo = 580
        robot.env.update(RACK_UP_MS=300)
        robot.tick = lambda delay: robot.buttons["B"]() if robot.servos[-1] == (1, 75) else None
        robot.buttons["A"]()
        self.assertEqual(robot.icon, 0)
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        previous = robot.servos[:]
        robot.env["drive_to_station"] = lambda delivering: self.fail("searched again after interrupted lift")
        robot.buttons["A"]()
        self.assertEqual(robot.icon, 0)
        self.assertEqual(robot.servos, previous)

    def test_cancel_during_drop(self):
        for command, delay in [((1, 105), 300), ((3, 45), 400), ((2, 45), 400)]:
            with self.subTest(command=command):
                robot = Robot()
                robot.echo = 580
                robot.env.update(GRIP_RIGHT_CLOSED=60, GRIP_LEFT_CLOSED=70, RACK_DOWN_MS=300,
                                 RACK_UP_MS=300)
                before_stop = []

                def tick(pause_ms):
                    if robot.carry_steps >= 7 and robot.servos[-1] == command:
                        self.assertEqual(pause_ms, delay)
                        before_stop.extend(robot.servos)
                        robot.buttons["B"]()

                robot.tick = tick
                robot.buttons["A"]()
                self.assertTrue(before_stop)
                self.assertEqual(robot.icon, 0)
                after_stop = robot.servos[len(before_stop):]
                self.assertEqual(after_stop[:1], [(1, 90)])
                self.assertTrue(all(cmd == (1, 90) for cmd in after_stop))
                self.assertEqual(robot.wheels, [(0, 0)] * 4)
                previous = robot.servos[:]
                robot.buttons["A"]()
                self.assertEqual(robot.servos, previous)

    def test_cancel_while_carrying_keeps_grip(self):
        robot = Robot()
        robot.echo = 580
        robot.env.update(GRIP_RIGHT_CLOSED=60, GRIP_LEFT_CLOSED=70)
        robot.tick = lambda delay: robot.buttons["B"]() if robot.carry_steps == 2 else None
        robot.buttons["A"]()
        self.assertEqual(robot.icon, 0)
        self.assertEqual(robot.env["carrying_color"], robot.pick_color)
        self.assertEqual([p for p in robot.servos if p[0] in (2, 3)][-2:], [(2, 70), (3, 60)])
        robot.tick = lambda delay: None
        robot.buttons["A"]()
        self.assertGreaterEqual(robot.carry_steps, 7)
        self.assertEqual(robot.icon, 1)
        self.assertEqual(robot.sensor_probes, 1)

    def test_missing_sensor_or_unrecognized_pickup(self):
        for ready, color in ((False, 1), (True, -1), (True, 0)):
            robot = Robot(sensor_present=ready)
            robot.echo, robot.pick_color = 580, color
            robot.buttons["A"]()
            self.assertEqual(robot.icon, 0)
            self.assertEqual(robot.env["carrying_color"], 0)

    def test_cancel_while_reversing(self):
        robot = Robot()
        robot.mask = 0
        robot.tick = lambda delay: robot.buttons["B"]() if robot.wheels[0][0] == -1 else None
        robot.buttons["A"]()
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        self.assertEqual(robot.servos, [(2, 45), (3, 45), (1, 90)])
        self.assertEqual(robot.icon, 0)


if __name__ == "__main__":
    unittest.main()
