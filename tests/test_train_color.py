"""Run with python tests/test_train_color.py (standard library only)."""
import importlib.util
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_search import Robot  # noqa: E402

SPEC = importlib.util.spec_from_file_location("train_color", ROOT / "tools" / "train_color.py")
train_color = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(train_color)

CENTERS = {
    0: (330, 320, 310),
    1: (650, 250, 150),
    2: (200, 260, 620),
    3: (210, 640, 180),
    4: (560, 500, 160),
}


def make_samples(seed=7, per_class=40, side="", labels=None):
    rng = random.Random(seed)
    samples = []
    for label in sorted(labels if labels is not None else CENTERS):
        for _ in range(per_class):
            clear = rng.randint(800, 1500)
            red, green, blue = (max(20, value + rng.randint(-50, 50)) for value in CENTERS[label])
            samples.append(train_color.Sample(
                label, clear, clear * red // 1000, clear * green // 1000, clear * blue // 1000, side))
    return samples


def load_model(snippet):
    namespace = {"number": float, "RIGHT_CHANNEL": 0, "LEFT_CHANNEL": 1}
    exec(compile(snippet, "color_model.py", "exec"), namespace)
    return namespace


class TrainColorTest(unittest.TestCase):
    def test_parse_robot_serial_lines(self):
        samples = train_color.parse_samples([
            "# SAMPLE,RIGHT,RED,clear,red,green,blue",
            "",
            "SAMPLE,RIGHT,RED,1000,650,250,140",
            "SAMPLE,LEFT,YELLOW,900,500,460,140",
            "BLUE,800,200,300,600",
            "SAMPLE,EMPTY,900,320,310,300",
        ])
        self.assertEqual([sample.label for sample in samples], [1, 4, 2, 0])
        self.assertEqual([sample.side for sample in samples], ["R", "L", "", ""])
        self.assertEqual(samples[0].clear, 1000)
        with self.assertRaises(ValueError):
            train_color.parse_samples(["PINK,900,300,300,300"])
        with self.assertRaises(ValueError):
            train_color.parse_samples(["RED,900,300"])

    def test_tree_learns_separated_colors(self):
        samples = make_samples()
        report = train_color.evaluate("", samples)
        self.assertGreaterEqual(report.train_accuracy, 0.99)
        self.assertGreaterEqual(report.cv_accuracy, 0.9)
        self.assertGreaterEqual(report.cv_accuracy, report.train_accuracy - 0.05)
        self.assertEqual(report.cv_k, 5)

    def test_shared_model_matches_tree(self):
        samples = make_samples()
        report = train_color.evaluate("", samples)
        namespace = load_model(train_color.emit_model([report]))
        model = namespace["model_color"]
        self.assertTrue(namespace["MODEL_READY"])
        for sample in samples:
            expected = report.tree.predict(sample.ratios())
            self.assertEqual(model(0, sample.clear, sample.red, sample.green, sample.blue), expected)
            self.assertEqual(model(1, sample.clear, sample.red, sample.green, sample.blue), expected)
        self.assertEqual(model(0, 5, 100, 100, 100), -1)

    def test_side_models_dispatch_by_channel(self):
        right = make_samples(seed=1, side="R", labels=[1, 2])
        left = make_samples(seed=2, side="L", labels=[3, 4])
        reports = [train_color.evaluate("R", right), train_color.evaluate("L", left)]
        snippet = train_color.emit_model(reports)
        self.assertIn("channel == RIGHT_CHANNEL", snippet)
        namespace = load_model(snippet)
        model = namespace["model_color"]
        for raw in [(1000, 650, 250, 150), (1000, 210, 640, 180), (1000, 560, 500, 160)]:
            sample = train_color.Sample(0, *raw)
            self.assertEqual(model(0, *raw), reports[0].tree.predict(sample.ratios()))
            self.assertEqual(model(1, *raw), reports[1].tree.predict(sample.ratios()))
        self.assertNotEqual(model(0, 1000, 650, 250, 150), model(1, 1000, 650, 250, 150))

    def test_select_reports_builds_side_groups(self):
        shared = train_color.select_reports(make_samples())
        self.assertEqual([report.side for report in shared], [""])
        both = train_color.select_reports(make_samples(side="R", labels=[1, 2]) +
                                          make_samples(seed=2, side="L", labels=[3, 4]))
        self.assertEqual([report.side for report in both], ["R", "L"])
        one_side = train_color.select_reports(make_samples(side="R", labels=[1, 2]))
        self.assertEqual([report.side for report in one_side], ["R"])

    def test_apply_model_replaces_block_once(self):
        main_text = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("MODEL_READY = False", main_text)
        snippet = train_color.emit_model([train_color.evaluate("", make_samples())])
        patched = train_color.apply_model(main_text, snippet)
        self.assertIn("MODEL_READY = True", patched)
        self.assertEqual(patched.count(train_color.BEGIN_MARKER), 1)
        compile(patched, "patched_main.py", "exec")
        self.assertEqual(patched, train_color.apply_model(patched, snippet))

    def test_threshold_baseline_keeps_old_behavior(self):
        cases = [((150, 80, 72, 18), 4), ((150, 95, 30, 25), 1), ((150, 26, 88, 22), 3),
                 ((150, 22, 35, 85), 2), ((150, 55, 55, 55), 0), ((0, 0, 0, 0), -1)]
        for (clear, red, green, blue), expected in cases:
            with self.subTest(sample=(clear, red, green, blue)):
                self.assertEqual(train_color.rule_color(clear, red, green, blue), expected)

    def test_read_color_uses_applied_model_on_both_channels(self):
        robot = Robot()
        patched = train_color.apply_model(
            (ROOT / "main.py").read_text(encoding="utf-8"),
            train_color.emit_model([train_color.evaluate("", make_samples())]))
        env = dict(robot.env)
        exec(compile(patched, "patched_main.py", "exec"), env)
        read_color = env["read_color"]

        robot.samples = [(1000, 650, 250, 150), (1000, 560, 500, 160)]
        self.assertEqual(read_color(0), 1)
        self.assertEqual(read_color(1), 4)
        robot.samples = [(1000, 330, 320, 310), (1000, 200, 260, 620)]
        self.assertEqual(read_color(0), 0)
        self.assertEqual(read_color(1), 2)
        robot.samples = [(10, 0, 0, 0), (10, 0, 0, 0)]
        self.assertEqual(read_color(0), -1)
        self.assertEqual(read_color(1), -1)


if __name__ == "__main__":
    unittest.main()
