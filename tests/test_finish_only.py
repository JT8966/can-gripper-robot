"""Run with python tests/test_finish_only.py."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


class FinishRouteTest(unittest.TestCase):
    def simulate(self, stop_at=None):
        wheels = [0] * 4
        powers = [0] * 4
        moves, buttons = [], {}

        def run_motor(channel, direction, power):
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
        buttons["A"]()
        self.assertEqual(wheels, [0] * 4)
        return api, moves

    def test_follows_example_map_to_finish(self):
        api, moves = self.simulate()
        heading, col, row = 0, 1, 4
        corners = []
        for wheels, duration in moves:
            if wheels == (1, 1, 1, 1):
                tiles, remainder = divmod(duration, api["TILE_MS"])
                self.assertEqual(remainder, 0)
                dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][heading]
                col, row = col + dx * tiles, row + dy * tiles
                corners.append((col, row))
            elif wheels == (1, 1, -1, -1):
                heading = (heading + 1) % 4
                self.assertEqual(duration, api["RIGHT_90_MS"])
            else:
                self.assertEqual(wheels, (-1, -1, 1, 1))
                heading = (heading - 1) % 4
                self.assertEqual(duration, api["LEFT_90_MS"])
        self.assertEqual(corners, [(1, 1), (3, 1), (3, 2), (2, 2), (2, 3), (7, 3), (7, 4)])

    def test_stop_during_forward_or_pivot(self):
        for step in (1, 2, 13):
            with self.subTest(step=step):
                _, moves = self.simulate(stop_at=step)
                self.assertEqual(len(moves), step)


if __name__ == "__main__":
    unittest.main()
