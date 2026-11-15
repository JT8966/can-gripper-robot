"""Run with python tests/test_finish_only.py."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


class FinishRouteTest(unittest.TestCase):
    def simulate(self, stop_at=None, repeat_at=None, fail_at=None):
        wheels = [0] * 4
        powers = [0] * 4
        moves, buttons = [], {}

        def run_motor(channel, direction, power):
            self.assertFalse(api["stopped"], "motor restarted after B")
            self.assertIn(channel, (1, 2, 3, 4))
            wheels[channel - 1] = direction
            powers[channel - 1] = power

        def pause(duration):
            if any(wheels):
                if wheels == [1, 1, 1, 1]:
                    self.assertEqual(powers, [api["LEFT_FORWARD_SPEED"]] * 2 + [api["RIGHT_FORWARD_SPEED"]] * 2)
                else:
                    self.assertEqual(powers, [api["TURN_SPEED"]] * 4)
                moves.append((tuple(wheels), duration))
                if len(moves) == stop_at:
                    buttons["B"]()
                    self.assertEqual(wheels, [0] * 4)
                if len(moves) == repeat_at:
                    buttons["A"]()
                if len(moves) == fail_at:
                    raise RuntimeError("simulated runtime failure")

        def brake(channel):
            self.assertEqual(channel, 0)
            wheels[:] = [0] * 4
            powers[:] = [0] * 4

        api = dict(MotionBitMotorChannel=NS(ALL=0, M1=1, M2=2, M3=3, M4=4),
                   MotionBitMotorDirection=NS(FORWARD=1, BACKWARD=-1),
                   motionbit=NS(run_motor=run_motor, brake_motor=brake),
                   basic=NS(pause=pause, clear_screen=lambda: None, show_string=lambda s: None),
                   input=NS(on_button_pressed=buttons.__setitem__), Button=NS(A="A", B="B"))
        source = Path(__file__).resolve().parents[1] / "finish-only" / "main.py"
        exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), api)
        self.assertEqual(moves, [])
        if fail_at is None:
            buttons["A"]()
        else:
            with self.assertRaisesRegex(RuntimeError, "simulated runtime failure"):
                buttons["A"]()
        self.assertEqual(wheels, [0] * 4)
        self.assertFalse(api["running"])
        return api, moves

    def test_visits_checkpoints_without_crossing_mapped_walls(self):
        api, moves = self.simulate()
        heading, col, row = 1, 3, 4
        visited = [(col, row)]
        vertical_walls = {(3, 1), (3, 2), (6, 1), (1, 2), (1, 3), (1, 4),
                          (4, 2), (5, 2), (6, 4), (7, 4), (2, 4)}
        horizontal_walls = {(2, 1), (8, 1), (3, 2), (4, 2), (5, 2),
                            (7, 2), (8, 2), (3, 3), (4, 3)}
        for wheels, duration in moves:
            if wheels == (1, 1, 1, 1):
                tiles, remainder = divmod(duration, api["TILE_MS"])
                self.assertEqual(remainder, 0)
                dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][heading]
                for _ in range(tiles):
                    if dx:
                        self.assertNotIn((min(col, col + dx), row), vertical_walls)
                    if dy:
                        self.assertNotIn((col, min(row, row + dy)), horizontal_walls)
                    col, row = col + dx, row + dy
                    self.assertTrue(1 <= col <= 8 and 1 <= row <= 4)
                    visited.append((col, row))
            elif wheels == (1, 1, -1, -1):
                heading = (heading + 1) % 4
                self.assertEqual(duration, api["RIGHT_90_MS"])
            else:
                self.assertEqual(wheels, (-1, -1, 1, 1))
                heading = (heading - 1) % 4
                self.assertEqual(duration, api["LEFT_90_MS"])
        self.assertEqual(visited, [(3, 4), (4, 4), (5, 4), (6, 4), (6, 3),
                                   (7, 3), (7, 4), (7, 3), (6, 3), (6, 2),
                                   (7, 2), (7, 1), (7, 2), (6, 2), (6, 1),
                                   (5, 1), (5, 2)])
        self.assertLess(visited.index((7, 4)), visited.index((7, 1)))
        self.assertEqual((col, row, heading), (5, 2, 2))

    def test_stop_during_every_forward_or_pivot(self):
        api, _ = self.simulate()
        for step in range(1, len(api["ROUTE"]) + 1):
            with self.subTest(step=step):
                _, moves = self.simulate(stop_at=step)
                self.assertEqual(len(moves), step)

    def test_repeated_start_does_not_restart_route(self):
        _, expected = self.simulate()
        _, actual = self.simulate(repeat_at=1)
        self.assertEqual(actual, expected)

    def test_runtime_failure_brakes_and_unlocks_start(self):
        for step in (1, 2):
            with self.subTest(step=step):
                _, moves = self.simulate(fail_at=step)
                self.assertEqual(len(moves), step)


if __name__ == "__main__":
    unittest.main()
