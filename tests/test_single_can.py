from pathlib import Path
import unittest

from test_search import Robot


SOURCE = Path(__file__).resolve().parents[1] / "single-can" / "main.py"


class SingleRobot(Robot):
    def __init__(self, **kwargs):
        super().__init__(source=SOURCE, **kwargs)
        self.echo = 580
        self.missing_channel = 1
        self.samples_read = 0

    def pulse(self, pin, level, timeout):
        assert pin == 1
        assert not self.env["can_color"]
        return self.echo

    def read_sample(self, addr, size):
        self.samples_read += 1
        return super().read_sample(addr, size)

    def follow_heading(self, delay):
        left, right = self.wheels[0][0], self.wheels[2][0]
        if left == -right and left:
            self.heading = (self.heading + 6 * left) % 360


class SingleCanTest(unittest.TestCase):
    def test_full_route_each_color_once(self):
        for sample, station, facing in [((150, 95, 30, 25), "EE", 2),
                                        ((150, 26, 88, 22), "WWWW", 2),
                                        ((150, 80, 72, 18), "NEN", 1)]:
            with self.subTest(station=station):
                robot = SingleRobot()
                robot.samples[0] = sample
                robot.tick = robot.follow_heading
                paths, faces = [], []
                walk = robot.env["walk_path"]
                face = robot.env["face_field"]
                def trace_path(path, returning=False):
                    paths.append((path, returning))
                    return walk(path, returning)
                def trace_face(direction):
                    faces.append(direction)
                    return face(direction)
                robot.env["walk_path"] = trace_path
                robot.env["face_field"] = trace_face
                robot.buttons["A"]()
                self.assertEqual(robot.icon, 1)
                self.assertEqual(paths, [("EEEN", False), ("NE", False),
                                         ("NE", True), (station, False)])
                self.assertEqual(faces[-1], facing)
                self.assertEqual(robot.samples_read, 5)
                self.assertEqual(robot.sensor_probes, [0])
                self.assertEqual([s for s in robot.servos if s[0] == 3],
                                 [(3, 40), (3, 10), (3, 40)])
                self.assertEqual([s for s in robot.servos if s[0] == 2], [(2, 40)])
                self.assertEqual(robot.env["can_color"], 0)
                self.assertEqual(robot.wheels, [(0, 0)] * 4)
                before = list(robot.servos)
                robot.buttons["A"]()
                self.assertEqual(robot.servos, before)

    def test_lock_persists_without_rereading_until_release(self):
        robot = SingleRobot()
        self.assertTrue(robot.env["pick_can"]())
        self.assertEqual(robot.env["can_color"], 1)
        robot.samples[0] = (150, 26, 88, 22)
        self.assertFalse(robot.env["pick_can"]())
        self.assertTrue(robot.env["place_can"]())
        self.assertEqual(robot.samples_read, 5)
        self.assertEqual(robot.env["can_color"], 0)

    def test_reject_invalid_or_unavailable_color(self):
        for sample in [(0, 0, 0, 0), (150, 55, 55, 55), (150, 22, 35, 85)]:
            robot = SingleRobot()
            robot.samples[0] = sample
            self.assertFalse(robot.env["pick_can"]())
            self.assertEqual(robot.env["can_color"], 0)
            self.assertNotIn((3, 10), robot.servos)
        for failure in ("mux", "sensor"):
            robot = SingleRobot()
            if failure == "mux":
                robot.mux_present = False
            else:
                robot.sensor_present = False
            self.assertFalse(robot.env["pick_can"]())
            self.assertNotIn((3, 10), robot.servos)

    def test_unstable_fifth_read_does_not_grip(self):
        robot = SingleRobot()
        def change(delay):
            if robot.samples_read == 4:
                robot.samples[0] = (150, 26, 88, 22)
        robot.tick = change
        self.assertFalse(robot.env["pick_can"]())
        self.assertEqual(robot.samples_read, 5)
        self.assertEqual(robot.env["can_color"], 0)
        self.assertNotIn((3, 10), robot.servos)

    def test_stop_and_boundary_loss_during_lock(self):
        for stop in (True, False):
            robot = SingleRobot()
            def interrupt(delay):
                if robot.samples_read == 4:
                    if stop:
                        robot.buttons["B"]()
                    else:
                        robot.mask = 0
            robot.tick = interrupt
            self.assertFalse(robot.env["pick_can"]())
            self.assertEqual(robot.env["can_color"], 0)
            self.assertNotIn((3, 10), robot.servos)

    def test_stop_during_drive_grip_lift_and_release(self):
        for stage in ("drive", "grip", "lift", "drop_lift", "release"):
            with self.subTest(stage=stage):
                robot = SingleRobot()
                fired = False
                def interrupt(delay):
                    nonlocal fired
                    robot.follow_heading(delay)
                    ups = robot.servos.count((1, 75))
                    trigger = ((stage == "drive" and robot.wheels[0][0] != 0)
                               or (stage == "grip" and (3, 10) in robot.servos and ups == 0)
                               or (stage == "lift" and ups == 1)
                               or (stage == "drop_lift" and ups == 2)
                               or (stage == "release" and robot.servos.count((3, 40)) == 2))
                    if not fired and trigger:
                        fired = True
                        robot.buttons["B"]()
                robot.tick = interrupt
                robot.buttons["A"]()
                self.assertTrue(fired)
                self.assertEqual(robot.icon, 0)
                self.assertEqual(robot.wheels, [(0, 0)] * 4)
                self.assertEqual(robot.servos[-1], (1, 90))
                if stage not in ("drive", "release"):
                    self.assertEqual(robot.env["can_color"], 1)
                    self.assertEqual(robot.servos.count((3, 40)), 1)
                before = list(robot.servos)
                robot.buttons["A"]()
                self.assertEqual(robot.servos, before)

    def test_approach_is_bounded_without_echo(self):
        robot = SingleRobot()
        robot.echo = 0
        self.assertFalse(robot.env["pick_can"]())
        self.assertLessEqual(robot.env["dock_travel_ms"], robot.env["FIELD_TILE_MS"])
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        self.assertNotIn((3, 10), robot.servos)

    def test_boundary_loss_and_turn_timeout_stop(self):
        robot = SingleRobot()
        robot.mask = 0
        robot.buttons["A"]()
        self.assertEqual(robot.icon, 0)
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        robot = SingleRobot()
        robot.env["field_north"] = 0
        self.assertFalse(robot.env["face_field"](1))
        self.assertEqual(robot.wheels, [(0, 0)] * 4)

    def test_exception_stops_wheels_and_rack(self):
        robot = SingleRobot()
        def fail():
            raise RuntimeError("I2C failure")
        robot.env["run_delivery"] = fail
        with self.assertRaises(RuntimeError):
            robot.buttons["A"]()
        self.assertFalse(robot.env["busy"])
        self.assertTrue(robot.env["cycle_started"])
        self.assertEqual(robot.wheels, [(0, 0)] * 4)
        self.assertEqual(robot.servos[-1], (1, 90))

    def test_stop_before_start(self):
        robot = SingleRobot()
        robot.buttons["B"]()
        before = list(robot.servos)
        robot.buttons["A"]()
        self.assertEqual(robot.servos, before)
        self.assertFalse(robot.env["cycle_started"])


if __name__ == "__main__":
    unittest.main()
