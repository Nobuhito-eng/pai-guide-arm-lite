"""Standard-library TF-IDF / multinomial-logistic inference; no network or pickle.

The weights are learned by scripts/train_model.py, NOT keyword-to-motion rules.
Guard rules may only HOLD an input; they never choose a movement.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"reception": "受付 / A方向", "exit": "出口 / B方向", "hold": "保留 / 新規指令なし"}
REASONS = {
    "empty": "依頼が空です。目的を具体的に入力してください。",
    "too_long": "長文は対象外です。120文字以内で一つの目的を入力してください。",
    "control_chars": "制御文字を含む入力は受け付けません。",
    "stop_or_negation": "停止・否定を含む依頼は保留します。必要な案内先を肯定文で指定してください。",
    "multiple_destinations": "複数の案内先を含む依頼は保留します。一つずつ入力してください。",
    "unknown": "既知の文字特徴が不足しています。受付または出口への目的を具体化してください。",
    "low_score": "分類スコアが基準未満のため保留しました。",
    "small_margin": "上位候補の差が小さいため保留しました。",
    "model_hold": "AIが対象外・曖昧な依頼と判定しました。",
    "classified": "学習済み分類器の判定に従い、登録済みの案内姿勢を選択します。",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


@dataclass(frozen=True)
class Decision:
    label: str
    reason: str
    scores: dict[str, float]
    top_label: str | None = None
    margin: float = 0.0
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Classifier:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else ROOT / "model" / "intent_model.json"
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        d = json.loads(raw.decode("utf-8"))
        if d.get("format") != "guide-lite-tfidf-logreg-v1":
            raise ValueError("Unsupported model format")
        self.classes = d["classes"]
        self.vocab = d["vocabulary"]
        self.idf = d["idf"]
        self.coef = d["coef"]
        self.intercept = d["intercept"]
        self.ngram_range = d["ngram_range"]
        self.threshold = d["hold_threshold"]
        self.margin_threshold = d["margin_threshold"]
        n = len(self.idf)
        if set(self.classes) != set(LABELS) or len(self.classes) != 3:
            raise ValueError("Model must have exactly three expected classes")
        if len(self.vocab) != n or set(self.vocab.values()) != set(range(n)):
            raise ValueError("Invalid vocabulary dimensions")
        if len(self.coef) != 3 or any(len(c) != n for c in self.coef) or len(self.intercept) != 3:
            raise ValueError("Invalid coefficient dimensions")
        values = self.idf + self.intercept + [v for row in self.coef for v in row]
        if not all(math.isfinite(v) for v in values) or any(v <= 0 for v in self.idf):
            raise ValueError("Invalid model numbers")
        if not 0 <= self.threshold <= 1 or not 0 <= self.margin_threshold <= 1:
            raise ValueError("Invalid thresholds")

    def features(self, text: str) -> dict[int, float]:
        s = normalize(text)
        counts: Counter[int] = Counter()
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            for i in range(len(s) - n + 1):
                idx = self.vocab.get(s[i:i+n])
                if idx is not None:
                    counts[idx] += 1
        weights = {i: count * self.idf[i] for i, count in counts.items()}
        norm = math.sqrt(sum(v*v for v in weights.values()))
        return {i: v / norm for i, v in weights.items()} if norm else {}

    def predict_proba(self, text: str) -> dict[str, float]:
        x = self.features(text)
        logits = [b + sum(row[i] * v for i, v in x.items())
                  for row, b in zip(self.coef, self.intercept)]
        largest = max(logits)
        exponentials = [math.exp(v - largest) for v in logits]
        denom = sum(exponentials)
        return dict(zip(self.classes, (v / denom for v in exponentials)))

    def decide(self, text: str) -> Decision:
        if not isinstance(text, str):
            raise TypeError("Input must be a string")
        if any(unicodedata.category(c) in ("Cc", "Cf") for c in text):
            return Decision("hold", "control_chars", {})
        s = normalize(text)
        if not s:
            return Decision("hold", "empty", {})
        if len(s) > 120:
            return Decision("hold", "too_long", {})
        scores = self.predict_proba(s)
        ranked = sorted(scores, key=scores.get, reverse=True)
        top = ranked[0]
        margin = scores[top] - scores[ranked[1]]
        reason = "classified"
        if re.search(r"ない|なく|ません|やめ|止め|停止|違う|ちがう|キャンセル", s):
            reason = "stop_or_negation"
        elif (re.search(r"受付|受け付け|窓口|手続き|チェックイン", s)
              and re.search(r"出口|退館|外に|帰り", s)):
            reason = "multiple_destinations"
        elif not self.features(s):
            reason = "unknown"
        elif top == "hold":
            reason = "model_hold"
        elif scores[top] < self.threshold:
            reason = "low_score"
        elif margin < self.margin_threshold:
            reason = "small_margin"
        label = top if reason == "classified" else "hold"
        return Decision(label, reason, scores, top, margin)


def load_motion_config(path: Path | str | None = None) -> dict[str, Any]:
    d = json.loads(Path(path or ROOT / "config" / "motion.json").read_text(encoding="utf-8"))
    expected = [f"crane_plus_joint{i}" for i in range(1, 5)]
    if d["joint_names"] != expected or set(d["poses"]) != {"home", "reception", "exit"}:
        raise ValueError("Unexpected joints or poses: use CRANE+ V2 simulator only")
    for name, pose in d["poses"].items():
        if len(pose) != 4 or not all(math.isfinite(v) and abs(v) <= 1.2 for v in pose):
            raise ValueError(f"Invalid or excessive pose: {name}")
    if not 2 <= d["duration_s"] <= 10:
        raise ValueError("duration_s must be in [2,10]")
    if not 0 < d["position_tolerance_rad"] <= .1:
        raise ValueError("Invalid position tolerance")
    if d["poses"]["reception"] == d["poses"]["exit"]:
        raise ValueError("Two destinations require different poses")
    return d


def plan_for(decision: Decision, config: dict[str, Any]) -> list[float] | None:
    """Only two whitelist labels can select a motion; HOLD sends nothing."""
    if decision.label == "hold":
        return None
    if decision.label not in ("reception", "exit"):
        raise ValueError("Unknown movement label")
    return list(config["poses"][decision.label])


def max_error(actual: list[float], target: list[float]) -> float:
    if len(actual) != len(target) or not actual:
        raise ValueError("Mismatching joint vectors")
    if not all(math.isfinite(x) for x in actual + target):
        raise ValueError("Non-finite joint state")
    return max(abs(a-b) for a, b in zip(actual, target))


def code_fingerprint() -> str:
    """Fingerprint executable application sources, independent of absolute paths."""
    h = hashlib.sha256()
    paths = [ROOT / "guide.py"] + sorted((ROOT / "guide_lite").glob("*.py"))
    for path in paths:
        h.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        h.update(path.read_bytes())
    return h.hexdigest()
