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
        self.sensor_present = sensor_present
        self.mux_mask = 0
        self.mux_present = True
        self.missing_channel = -1
        self.sensor_probes = []
        self.icon = None
        self.display = ""
        self.tick = lambda delay: None
        self.samples = [(150, 95, 30, 25), (150, 95, 30, 25)]
        self.env = dict(
            number=float, DigitalPin=NS(**{f"P{i}": i for i in range(17)}),
            MotionBitMotorChannel=NS(ALL=0, M1=1, M2=2, M3=3, M4=4),
            MotionBitMotorDirection=NS(FORWARD=1, BACKWARD=-1),
            MotionBitServoChannel=NS(S1=1, S2=2, S3=3),
            Button=NS(A="A", B="B"),
            IconNames=NS(YES=1, NO=0),
            ArrowNames=NS(NORTH=0, EAST=2, SOUTH=4, WEST=6),
            input=NS(on_button_pressed=self.buttons.__setitem__, running_time=lambda: self.ms,
                     compass_heading=lambda: self.heading, calibrate_compass=lambda: None,
                     button_is_pressed=lambda button: False),
            PulseValue=NS(HIGH=1), NumberFormat=NS(UINT8_LE=0, UINT16_LE=1),
            pins=NS(digital_read_pin=lambda p: (self.mask >> (p - 12)) & 1,
                    digital_write_pin=self.trig, pulse_in=self.pulse,
                    i2c_write_number=self.write_i2c, i2c_write_buffer=lambda *args: None,
                    i2c_read_number=self.read_i2c, i2c_read_buffer=self.read_sample),
            motionbit=NS(run_motor=self.drive, brake_motor=self.brake, set_servo_position=self.servo),
            basic=NS(pause=self.pause, clear_screen=lambda: None, show_string=lambda text: None,
                     show_icon=lambda icon, interval=0: setattr(self, "icon", icon),
                     show_leds=lambda pattern, interval: setattr(self, "display", pattern)),
            control=NS(wait_micros=lambda delay: None), serial=NS(write_line=lambda text: None),
        )
        exec(compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec"), self.env)
        self.classify = self.env["read_color"]

    def write_i2c(self, addr, value, fmt, repeated=False):
        if addr == 0x70:
            assert not repeated and value in (1, 2)
            self.mux_mask = value if self.mux_present else 0
        else:
            assert addr == 0x29 and repeated and self.mux_mask in (1, 2)

    def read_i2c(self, addr, fmt):
        if addr == 0x70:
            return self.mux_mask
        assert addr == 0x29
        channel = self.mux_mask - 1
        self.sensor_probes.append(channel)
        return 0x44 if self.sensor_present and channel != self.missing_channel else 0

    def read_sample(self, addr, size):
        assert addr == 0x29 and size == 8 and self.mux_mask in (1, 2)
        sample = self.samples[self.mux_mask - 1]
        return NS(get_number=lambda fmt, offset: sample[offset // 2])

    def trig(self, pin, value):
        assert pin == 0

    def pulse(self, pin, level, timeout):
        assert pin == 1
        assert not self.env["right_can_color"] and not self.env["left_can_color"]
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
        self.tick(delay)


class SearchTest(unittest.TestCase):
    def test_color_sensor_required(self):
        robot = Robot(sensor_present=False)
        self.assertFalse(robot.env["color_sensor_ready"])
        def arrive(delay):
            if robot.wheels[0][0] == 1:
                robot.echo = 580
        robot.tick = arrive
        self.assertFalse(robot.env["pick_cans"]())
        self.assertEqual(robot.echo, 580)
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        self.assertEqual(robot.servos, [(2, 40), (3, 40)])
        robot.sensor_present = True
        self.assertTrue(robot.env["pick_cans"]())
        self.assertTrue(robot.env["color_sensor_ready"])

    def test_rgb_samples(self):
        robot = Robot()
        for sample, expected in [((150, 80, 72, 18), 4), ((150, 95, 30, 25), 1),
                                 ((150, 26, 88, 22), 3), ((150, 22, 35, 85), 2),
                                 ((150, 55, 55, 55), 0), ((0, 0, 0, 0), -1)]:
            with self.subTest(sample=sample):
                buf = NS(get_number=lambda fmt, offset: sample[offset // 2])
                robot.env["pins"].i2c_read_buffer = lambda addr, n: buf
                robot.env["NumberFormat"].UINT16_LE = 1
                self.assertEqual(robot.classify(0), expected)

    def test_unavailable_mux_or_one_sensor(self):
        for mux_present, missing in [(False, -1), (True, 0), (True, 1)]:
            robot = Robot()
            robot.echo, robot.mux_present, robot.missing_channel = 580, mux_present, missing
            self.assertFalse(robot.env["pick_cans"]())
            self.assertEqual(robot.servos, [(2, 40), (3, 40)])
            robot.mux_present, robot.missing_channel = True, -1
            robot.samples[1] = (150, 26, 88, 22)
            self.assertTrue(robot.env["pick_cans"]())
            self.assertEqual((robot.env["right_can_color"], robot.env["left_can_color"]), (1, 3))

    def test_search_and_grip(self):
        for drift, turn_step in [(15, 15), (-15, 15), (15, 16)]:
            with self.subTest(drift=drift, turn_step=turn_step):
                robot = Robot()
                self.assertEqual((robot.ms, robot.servos), (1000, [(2, 40), (3, 40)]))
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
                self.assertTrue(robot.env["pick_cans"]())
                self.assertTrue(corrected)
                self.assertEqual(reverse_times, [50, 50])
                self.assertEqual(turns, [80, 170] if turn_step == 15 else [86, 182])
                self.assertEqual(robot.servos[2:], [(2, 10), (3, 10), (1, 75), (1, 90)])
                self.assertEqual(robot.wheels, [(0, 0)] * 4)

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
                found = robot.env["pick_cans"]()
                self.assertTrue(aligned)
                self.assertEqual(found, action in ("recover", "turn"))
                self.assertEqual(robot.wheels, [(0, 0)] * 4)

    def test_place_release_sequence(self):
        robot = Robot()
        robot.env.update(right_can_color=4, left_can_color=3)
        self.assertTrue(robot.env["place_cans"](4))
        self.assertEqual(robot.servos[2:], [(1, 75), (1, 90), (3, 40), (1, 105), (1, 90)])
        self.assertEqual(robot.env["left_can_color"], 3)
        self.assertFalse(robot.env["arm_cycle_incomplete"])
        self.assertFalse(robot.env["place_cans"](0))
        self.assertTrue(robot.env["place_cans"](3))
        self.assertEqual(robot.servos[7:], [(1, 75), (1, 90), (2, 40), (1, 105), (1, 90), (1, 105), (1, 90)])

    def test_cancel_during_pickup_lift_requires_reset(self):
        robot = Robot()
        robot.echo = 580
        robot.env.update(RACK_UP_MS=300)
        robot.tick = lambda delay: robot.buttons["B"]() if robot.servos[-1] == (1, 75) else None
        self.assertFalse(robot.env["pick_cans"]())
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        previous = robot.servos[:]
        robot.env["find_cans"] = lambda: self.fail("searched again after interrupted lift")
        self.assertFalse(robot.env["pick_cans"]())
        self.assertEqual(robot.servos, previous)

    def test_unrecognized_or_changing_can_color(self):
        for samples in [[0, 1], [-1, 1], [2, 1], [1, 3, 4], [1, 3, 1, 4]]:
            with self.subTest(samples=samples):
                robot = Robot()
                robot.echo = 580
                readings = iter(samples)
                robot.env["read_color"] = lambda channel: next(readings)
                self.assertFalse(robot.env["pick_cans"]())
                self.assertEqual(robot.env["right_can_color"], 0)
                self.assertEqual(robot.servos, [(2, 40), (3, 40)])

    def test_cancel_while_reversing(self):
        robot = Robot()
        robot.mask = 0
        robot.tick = lambda delay: robot.buttons["B"]() if robot.wheels[0][0] == -1 else None
        self.assertFalse(robot.env["pick_cans"]())
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        self.assertEqual(robot.servos[-1:], [(1, 90)])

    def test_failed_navigation_stops_before_pickup(self):
        robot = Robot()
        robot.mask = 0
        self.assertFalse(robot.env["run_match"]())
        self.assertEqual(robot.servos[2:], [])
        self.assertEqual(robot.wheels, [(0, 0)] * 4)

    def test_match_full_run(self):
        for mixed, left_sample, left_stop in [
            (False, (150, 95, 30, 25), (8,3,2)),
            (True, (150, 26, 88, 22), (2,3,2)),
            (True, (150, 80, 72, 18), (7,1,1)),
        ]:
            robot = Robot()
            robot.echo = 580
            robot.samples[1] = left_sample
            col, row, direction = 3, 4, 1
            stops, pickups, visited = [], [], []
            def face(d):
                nonlocal direction
                direction = d
                return True
            def drive(ms, reverse=False):
                nonlocal col, row
                if ms == robot.env["DROP_APPROACH_MS"]:
                    if not reverse:
                        stops.append((col, row, direction))
                else:
                    self.assertFalse(reverse and ms > 0)
                    tiles, remainder = divmod(ms, robot.env["FIELD_TILE_MS"])
                    self.assertEqual(remainder, 0)
                    for _ in range(tiles):
                        dx, dy = [(0,-1),(1,0),(0,1),(-1,0)][direction]
                        # Walls in the field photo, keyed by the tile left of / above the wall.
                        if dx:
                            self.assertNotIn((min(col, col+dx), row),
                                [(3,1), (3,2), (6,1), (1,2), (1,3), (1,4), (4,2), (5,2), (7,4), (2,4)])
                        if dy:
                            self.assertNotIn((col, min(row, row+dy)),
                                [(2,1), (8,1), (3,2), (4,2), (5,2), (7,2), (8,2), (3,3), (4,3)])
                        col, row = col + dx, row + dy
                        self.assertTrue(1 <= col <= 8 and 1 <= row <= 4)
                        visited.append((col, row))
                return True
            pick = robot.env["pick_cans"]
            def pickup(at_dock):
                self.assertTrue(at_dock)
                pickups.append((col, row, direction))
                return pick(at_dock)
            robot.env.update(face_field=face, drive_straight=drive, pick_cans=pickup)
            self.assertTrue(robot.env["run_match"]())
            self.assertEqual(pickups, [(7,2,1), (4,1,2), (1,3,2)])
            self.assertEqual(stops, ([(8,3,2), left_stop] if mixed else [(8,3,2)]) * 3)
            self.assertIn((7,4), visited)
            self.assertIn((7,1), visited)
            self.assertEqual((col,row), (5,2))
            self.assertEqual(robot.servos.count((2, 10)), 3)
            self.assertEqual((robot.env["right_can_color"], robot.env["left_can_color"]), (0, 0))
            self.assertEqual(robot.wheels, [(0, 0)] * 4)


if __name__ == "__main__":
    unittest.main()
