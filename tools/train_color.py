#!/usr/bin/env python3
"""เทรน Decision Tree ขนาดเล็กจากค่าดิบของ TCS34725 แล้วสร้างโค้ด MakeCode Python

ข้อมูลมาจากโหมดเก็บตัวอย่างบนหุ่น (กด A+B ค้างตอนเปิดเครื่อง) ซึ่งพิมพ์ทาง Serial:
    SAMPLE,RIGHT,RED,1234,567,321,123
    SAMPLE,LEFT,RED,1201,544,290,118
หรือเตรียมไฟล์เองในรูปแบบ side,label,clear,red,green,blue โดย side เป็น RIGHT/LEFT
หรือเว้นว่างได้ (SAMPLE นำหน้าก็ได้) บรรทัดที่ขึ้นต้นด้วย # จะถูกข้าม

ตัวอย่าง:
    python tools/train_color.py tools/samples.csv
    python tools/train_color.py tools/samples.csv --apply main.py

สคริปต์ใช้แค่ standard library จึงรันได้ทุกเครื่องที่มี Python 3.8 ขึ้นไป
"""
import argparse
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LABEL_NAMES = {0: "NONE", 1: "RED", 2: "BLUE", 3: "GREEN", 4: "YELLOW"}
NAME_TO_LABEL = {"NONE": 0, "EMPTY": 0, "RED": 1, "BLUE": 2, "GREEN": 3, "YELLOW": 4}
SIDE_NAMES = {"R": "R", "RIGHT": "R", "L": "L", "LEFT": "L", "BOTH": "", "ALL": ""}
SIDE_TITLES = {"": "BOTH sensors", "R": "RIGHT sensor (S3)", "L": "LEFT sensor (S2)"}
FEATURES = ("r", "g", "b")
DARK_CLEAR = 30
BEGIN_MARKER = "# ----- BEGIN COLOR MODEL"
END_MARKER = "# ----- END COLOR MODEL -----"


@dataclass(frozen=True)
class Sample:
    label: int
    clear: int
    red: int
    green: int
    blue: int
    side: str = ""

    def ratios(self):
        divisor = self.clear if self.clear > 0 else 1
        return (self.red * 1000 // divisor,
                self.green * 1000 // divisor,
                self.blue * 1000 // divisor)


def parse_samples(lines):
    samples = []
    for line_number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if parts[0].upper() == "SAMPLE":
            parts = parts[1:]
        side = ""
        if parts and parts[0].upper() in SIDE_NAMES:
            side = SIDE_NAMES[parts[0].upper()]
            parts = parts[1:]
        if len(parts) < 5:
            raise ValueError("บรรทัด %d: ต้องมี label,clear,red,green,blue" % line_number)
        name = parts[0].upper()
        if name in NAME_TO_LABEL:
            label = NAME_TO_LABEL[name]
        else:
            try:
                label = int(name)
            except ValueError:
                raise ValueError("บรรทัด %d: รู้จักสี %s ไม่ได้ (ใช้ NONE/RED/BLUE/GREEN/YELLOW)" % (line_number, parts[0]))
            if label not in LABEL_NAMES:
                raise ValueError("บรรทัด %d: หมายเลขสีต้องอยู่ระหว่าง 0 ถึง 4" % line_number)
        try:
            clear, red, green, blue = (int(value) for value in parts[1:5])
        except ValueError:
            raise ValueError("บรรทัด %d: ค่า RGBC ต้องเป็นจำนวนเต็ม" % line_number)
        if min(clear, red, green, blue) < 0:
            raise ValueError("บรรทัด %d: ค่า RGBC ต้องไม่ติดลบ" % line_number)
        samples.append(Sample(label, clear, red, green, blue, side))
    return samples


def _majority(counts):
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _gini(counts, total):
    total = float(total)
    return 1.0 - sum((count / total) ** 2 for count in counts.values())


class Node:
    __slots__ = ("feature", "threshold", "left", "right", "label", "size")

    def __init__(self, counts, size):
        self.feature = -1
        self.threshold = 0
        self.left = None
        self.right = None
        self.label = _majority(counts)
        self.size = size

    def is_leaf(self):
        return self.left is None


class Tree:
    def __init__(self, max_depth=5, min_leaf=2):
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.root = None

    def fit(self, samples):
        xs = [sample.ratios() for sample in samples]
        ys = [sample.label for sample in samples]
        self.root = self._build(xs, ys, 0)
        return self

    def predict(self, ratios):
        node = self.root
        while not node.is_leaf():
            node = node.left if ratios[node.feature] <= node.threshold else node.right
        return node.label

    def _build(self, xs, ys, depth):
        counts = Counter(ys)
        node = Node(counts, len(ys))
        if depth >= self.max_depth or len(counts) < 2 or len(ys) < 2 * self.min_leaf:
            return node
        best = None
        best_gain = 0.0
        for feature in range(len(FEATURES)):
            values = sorted({x[feature] for x in xs})
            for low, high in zip(values, values[1:]):
                threshold = (low + high) // 2
                left_counts = Counter()
                right_counts = Counter()
                for x, y in zip(xs, ys):
                    if x[feature] <= threshold:
                        left_counts[y] += 1
                    else:
                        right_counts[y] += 1
                if len(left_counts) == 0 or len(right_counts) == 0:
                    continue
                if sum(left_counts.values()) < self.min_leaf or sum(right_counts.values()) < self.min_leaf:
                    continue
                total = float(len(ys))
                gain = (_gini(counts, len(ys))
                        - sum(left_counts.values()) / total * _gini(left_counts, sum(left_counts.values()))
                        - sum(right_counts.values()) / total * _gini(right_counts, sum(right_counts.values())))
                if gain > best_gain + 1e-12:
                    best = (feature, threshold)
                    best_gain = gain
        if best is None:
            return node
        feature, threshold = best
        left = [(x, y) for x, y in zip(xs, ys) if x[feature] <= threshold]
        right = [(x, y) for x, y in zip(xs, ys) if x[feature] > threshold]
        node.feature = feature
        node.threshold = threshold
        node.left = self._build([x for x, _ in left], [y for _, y in left], depth + 1)
        node.right = self._build([x for x, _ in right], [y for _, y in right], depth + 1)
        return node


def accuracy(tree, samples):
    if not samples:
        return 0.0
    correct = sum(1 for sample in samples if tree.predict(sample.ratios()) == sample.label)
    return correct / len(samples)


def stratified_folds(samples, k, seed=42):
    groups = {}
    for sample in samples:
        groups.setdefault(sample.label, []).append(sample)
    rng = random.Random(seed)
    folds = [[] for _ in range(k)]
    for label in sorted(groups):
        group = list(groups[label])
        rng.shuffle(group)
        for index, sample in enumerate(group):
            folds[index % k].append(sample)
    return folds


def cross_validate(samples, k=5, max_depth=5, min_leaf=2, seed=42):
    folds = stratified_folds(samples, k, seed)
    correct = 0
    for index in range(k):
        train = [sample for other, fold in enumerate(folds) if other != index for sample in fold]
        tree = Tree(max_depth, min_leaf).fit(train)
        correct += sum(1 for sample in folds[index] if tree.predict(sample.ratios()) == sample.label)
    return correct / len(samples)


# เกณฑ์เดิมใน main.py ใช้เทียบว่าโมเดลใหม่ดีขึ้นหรือไม่
def rule_color(clear, red, green, blue):
    if clear < DARK_CLEAR:
        return -1
    if min(red, green) > blue * 1.45 and max(red, green) <= min(red, green) * 1.35:
        return 4
    if red > green * 1.35 and red > blue * 1.35:
        return 1
    if green > red * 1.35 and green > blue * 1.35:
        return 3
    if blue > green * 1.2 and blue > red * 1.35:
        return 2
    return 0


@dataclass
class Report:
    side: str
    tree: Tree
    data: list
    labels: list
    counts: dict
    train_accuracy: float
    baseline_accuracy: float
    cv_accuracy: float = None
    cv_k: int = 0


def evaluate(side, samples, max_depth=5, min_leaf=2, use_cv=True):
    tree = Tree(max_depth, min_leaf).fit(samples)
    counts = Counter(sample.label for sample in samples)
    report = Report(
        side, tree, list(samples), sorted(counts), dict(counts),
        accuracy(tree, samples),
        sum(1 for sample in samples
            if rule_color(sample.clear, sample.red, sample.green, sample.blue) == sample.label) / len(samples),
    )
    k = min(5, min(counts.values())) if counts else 0
    if use_cv and k >= 2:
        report.cv_accuracy = cross_validate(samples, k=k, max_depth=max_depth, min_leaf=min_leaf)
        report.cv_k = k
    return report


def select_reports(samples, max_depth=5, min_leaf=2, use_cv=True):
    # ถ้ามีข้อมูลระบุฝั่ง แยกโมเดลตามเซ็นเซอร์ แถวที่ไม่ระบุฝั่งจะถูกใช้ร่วมทั้งสองโมเดล
    explicit = {sample.side for sample in samples if sample.side}
    if not explicit:
        return [evaluate("", samples, max_depth, min_leaf, use_cv)]
    reports = []
    for side in ("R", "L"):
        group = [sample for sample in samples if sample.side == side or sample.side == ""]
        if group:
            reports.append(evaluate(side, group, max_depth, min_leaf, use_cv))
    return reports


def _emit_node(node, depth, lines):
    pad = "    " * depth
    if node.is_leaf():
        lines.append(pad + "return %d  # %s" % (node.label, LABEL_NAMES[node.label]))
        return
    lines.append(pad + "if %s <= %d:" % (FEATURES[node.feature], node.threshold))
    _emit_node(node.left, depth + 1, lines)
    lines.append(pad + "else:")
    _emit_node(node.right, depth + 1, lines)


def emit_model(reports):
    lines = [BEGIN_MARKER + " (สร้างด้วย tools/train_color.py) -----"]
    for report in reports:
        summary = "# %s: %d samples | train %.1f%% | baseline %.1f%%" % (
            SIDE_TITLES[report.side], len(report.data),
            report.train_accuracy * 100, report.baseline_accuracy * 100)
        if report.cv_accuracy is not None:
            summary += " | %d-fold CV %.1f%%" % (report.cv_k, report.cv_accuracy * 100)
        lines.append(summary)
    lines += [
        "# สร้างใหม่ด้วย: python tools/train_color.py <ไฟล์ข้อมูล> --apply main.py",
        "MODEL_READY = True",
        "",
        "",
        "def model_color(channel: number, clear: number, red: number, green: number, blue: number):",
        "    if clear < %d:" % DARK_CLEAR,
        "        return -1",
        "    r = red * 1000 // clear",
        "    g = green * 1000 // clear",
        "    b = blue * 1000 // clear",
    ]
    if len(reports) == 1:
        _emit_node(reports[0].tree.root, 1, lines)
    else:
        right = [report for report in reports if report.side == "R"][0]
        left = [report for report in reports if report.side == "L"][0]
        lines.append("    if channel == RIGHT_CHANNEL:")
        _emit_node(right.tree.root, 2, lines)
        lines.append("    else:")
        _emit_node(left.tree.root, 2, lines)
    lines.append("")
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def apply_model(main_text, snippet):
    start = main_text.find(BEGIN_MARKER)
    if start < 0:
        raise ValueError("ไม่พบเครื่องหมาย BEGIN COLOR MODEL ใน main.py")
    end = main_text.find(END_MARKER, start)
    if end < 0:
        raise ValueError("ไม่พบเครื่องหมาย END COLOR MODEL ใน main.py")
    end += len(END_MARKER)
    while end < len(main_text) and main_text[end] in "\r\n":
        end += 1
    return main_text[:start] + snippet.rstrip("\r\n") + "\n\n" + main_text[end:]


def print_confusion(predict, samples, labels, title):
    print(title)
    print("true\\pred".ljust(10) + "".join(LABEL_NAMES[label].rjust(8) for label in labels))
    for actual in labels:
        row = Counter(predict(sample) for sample in samples if sample.label == actual)
        print(LABEL_NAMES[actual].ljust(10) + "".join(str(row.get(predicted, 0)).rjust(8) for predicted in labels))


def print_report(report):
    print("")
    print("== %s ==" % SIDE_TITLES[report.side])
    print("samples %d: %s" % (
        len(report.data), ", ".join("%s %d" % (LABEL_NAMES[label], report.counts[label]) for label in report.labels)))
    for label in report.labels:
        if report.counts[label] < 10:
            print("คำเตือน: %s มีแค่ %d ตัวอย่าง ควรเก็บให้ถึงอย่างน้อย 10" % (LABEL_NAMES[label], report.counts[label]))
    if report.cv_accuracy is not None:
        print("%d-fold CV: %.1f%%" % (report.cv_k, report.cv_accuracy * 100))
    else:
        print("ตัวอย่างบางสีน้อยกว่า 2 แถว จึงยังประเมิน CV ไม่ได้")
    print("เกณฑ์เดิมใน main.py: %.1f%%" % (report.baseline_accuracy * 100))
    print("Decision Tree (train): %.1f%%" % (report.train_accuracy * 100))
    if report.cv_accuracy is not None and report.cv_accuracy < report.baseline_accuracy:
        print("คำเตือน: CV ต่ำกว่าเกณฑ์เดิม อย่าเพิ่งใช้โมเดลนี้ เก็บตัวอย่างให้ครอบคลุมแสงและการหมุนกระป๋องเพิ่ม")
    print("")
    print_confusion(lambda sample: rule_color(sample.clear, sample.red, sample.green, sample.blue),
                    report.data, report.labels, "เกณฑ์เดิม")
    print("")
    print_confusion(lambda sample: report.tree.predict(sample.ratios()),
                    report.data, report.labels, "Decision Tree")


def main(argv=None):
    # คอนโซล Windows บางแบบเป็น cp1252 ทำให้ print ภาษาไทยแล้วพัง
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    parser = argparse.ArgumentParser(description="เทรน Decision Tree สีกระป๋องจากค่าดิบ TCS34725")
    parser.add_argument("csv", nargs="?", default="tools/samples.csv", help="ไฟล์ CSV จากโหมดเก็บตัวอย่าง")
    parser.add_argument("--apply", metavar="MAIN_PY", help="แทนช่วง COLOR MODEL ใน main.py ด้วยโมเดลใหม่")
    parser.add_argument("--max-depth", type=int, default=5, help="ความลึกสูงสุดของต้นไม้ (ค่าเริ่มต้น 5)")
    parser.add_argument("--min-leaf", type=int, default=2, help="จำนวนตัวอย่างน้อยสุดต่อใบ (ค่าเริ่มต้น 2)")
    parser.add_argument("--no-cv", action="store_true", help="ข้ามการประเมินแบบ k-fold")
    args = parser.parse_args(argv)

    path = Path(args.csv)
    try:
        samples = parse_samples(path.read_text(encoding="utf-8").splitlines())
    except (OSError, ValueError) as error:
        print("อ่านข้อมูลไม่ได้: " + str(error))
        return 2
    usable = [sample for sample in samples if sample.clear >= DARK_CLEAR]
    skipped = len(samples) - len(usable)
    if skipped:
        print("ข้ามตัวอย่างมืด clear < %d: %d แถว" % (DARK_CLEAR, skipped))
    if not usable:
        print("ไม่มีตัวอย่างที่ใช้เทรนได้")
        return 2
    if len({sample.label for sample in usable}) < 2:
        print("ต้องมีอย่างน้อย 2 สีขึ้นไป เก็บตัวอย่างเพิ่มแล้วรันใหม่")
        return 2

    reports = select_reports(usable, max_depth=args.max_depth, min_leaf=args.min_leaf, use_cv=not args.no_cv)
    explicit = {sample.side for sample in usable if sample.side}
    if explicit and len(explicit) == 1 and len(reports) == 1:
        print("มีข้อมูลเฉพาะฝั่ง %s จะใช้โมเดลเดียวกันทั้งสองหัว" % SIDE_TITLES[reports[0].side])
    for report in reports:
        print_report(report)

    snippet = emit_model(reports)
    print("")
    if args.apply:
        target = Path(args.apply)
        try:
            text = target.read_text(encoding="utf-8")
            target.write_text(apply_model(text, snippet), encoding="utf-8")
        except (OSError, ValueError) as error:
            print("เขียนโมเดลไม่ได้: " + str(error))
            return 2
        print("เขียนโมเดลลง %s แล้ว เปิด MakeCode แล้วกด Download เพื่อลงบอร์ด" % target)
    else:
        print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
