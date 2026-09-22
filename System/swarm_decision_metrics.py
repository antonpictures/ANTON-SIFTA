#!/usr/bin/env python3
"""Pure measurement mathematics for the J2 calibration slice.

Everything here is deterministic, model-free and unit-tested, so the numbers a calibration
report quotes are produced by reviewable arithmetic rather than by the harness that happens
to call it.

Standing laws carried by these functions:

* Raw softmax over declared option logits is **not** calibrated. ``fit_temperature`` is the
  only thing allowed to turn it into something called ``calibrated``, and it is fitted on the
  fit split only.
* Temperature scaling is monotone, so it **never** changes the argmax choice. Any change in
  accuracy between raw and calibrated is therefore an abstention effect, not a new decision —
  ``assert_choice_preserved`` exists to prove that in tests.
* Abstention is scored honestly: abstained rows leave the precision/recall denominators and
  are reported as lost coverage. They are never silently counted as correct.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

LogitsRow = tuple[Sequence[float], int]


def _as_float_list(values: Iterable[Any]) -> list[float]:
    return [float(v) for v in values]


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    """Numerically stable softmax with temperature scaling."""
    if temperature <= 0:
        raise ValueError("temperature must be > 0")
    scaled = [float(v) / float(temperature) for v in logits]
    peak = max(scaled)
    exps = [math.exp(v - peak) for v in scaled]
    total = sum(exps)
    if total <= 0 or not math.isfinite(total):
        raise ValueError("softmax denominator is not finite and positive")
    probs = [e / total for e in exps]
    if not all(math.isfinite(p) for p in probs):
        raise ValueError("non-finite probability produced from logits")
    return probs


def argmax(values: Sequence[float]) -> int:
    best = 0
    for index in range(1, len(values)):
        if values[index] > values[best]:
            best = index
    return best


def mean_nll(rows: Sequence[LogitsRow], temperature: float = 1.0) -> float:
    if not rows:
        raise ValueError("mean_nll needs at least one row")
    total = 0.0
    for logits, gold in rows:
        probs = softmax(logits, temperature)
        p = max(probs[int(gold)], 1e-12)
        total += -math.log(p)
    return total / len(rows)


def fit_temperature(rows: Sequence[LogitsRow], *, grid: Sequence[float] | None = None,
                    refine_rounds: int = 6, max_temperature: float = 10.0) -> dict[str, Any]:
    """Fit a single temperature by minimising held-in NLL, then refine locally.

    A coarse multiplicative grid followed by bisection refinement. One parameter only, fitted
    on the fit split — deliberately the simplest calibrator that can be audited by hand.

    The refinement is capped at ``max_temperature`` and reports ``hit_cap``. A fit that runs
    into the cap means the model's stated confidence carried little information on the fit
    split; that is reported as the cap being hit rather than hidden behind a large number.
    """
    if not rows:
        raise ValueError("fit_temperature needs at least one row")
    cap = float(max_temperature)
    if cap <= 0:
        raise ValueError("max_temperature must be > 0")
    candidates = list(grid) if grid is not None else [0.25, 0.4, 0.5, 0.65, 0.8, 1.0,
                                                      1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0]
    candidates = [float(t) for t in candidates if 0 < float(t) <= cap]
    if not candidates:
        candidates = [cap]
    scored = [(mean_nll(rows, t), float(t)) for t in candidates]
    scored.sort()
    best_nll, best_t = scored[0]
    span = 0.5 * best_t
    for _ in range(max(0, int(refine_rounds))):
        improved = False
        for step in (-span, span):
            trial = min(cap, best_t + step)
            if trial <= 0 or trial == best_t:
                continue
            trial_nll = mean_nll(rows, trial)
            if trial_nll < best_nll - 1e-12:
                best_nll, best_t, improved = trial_nll, trial, True
        if not improved:
            span *= 0.5
    nll_before = mean_nll(rows, 1.0)
    return {
        "temperature": round(best_t, 6),
        "nll_before": round(nll_before, 6),
        "nll_after": round(best_nll, 6),
        "nll_improved": best_nll < nll_before - 1e-12,
        "n_rows": len(rows),
        "fitted_on": "fit split only",
        "grid": candidates,
        "max_temperature": cap,
        "hit_cap": best_t >= cap - 1e-9,
    }


def assert_choice_preserved(rows: Sequence[Sequence[float]], temperature: float) -> bool:
    """True when temperature scaling leaves every argmax unchanged (it must)."""
    for logits in rows:
        if argmax(logits) != argmax(softmax(logits, temperature)):
            return False
    return True


def confusion_matrix(pairs: Sequence[tuple[int, int]], n_classes: int) -> list[list[int]]:
    matrix = [[0] * n_classes for _ in range(n_classes)]
    for gold, predicted in pairs:
        matrix[int(gold)][int(predicted)] += 1
    return matrix


def classification_metrics(pairs: Sequence[tuple[int, int]],
                           labels: Sequence[str]) -> dict[str, Any]:
    """Per-class precision/recall/F1, accuracy and macro-F1 over *answered* predictions."""
    n_classes = len(labels)
    matrix = confusion_matrix(pairs, n_classes)
    per_class: dict[str, dict[str, Any]] = {}
    f1s: list[float] = []
    for index, label in enumerate(labels):
        tp = matrix[index][index]
        fp = sum(matrix[row][index] for row in range(n_classes) if row != index)
        fn = sum(matrix[index][col] for col in range(n_classes) if col != index)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        if precision is None or recall is None or (precision + recall) == 0:
            f1 = 0.0 if (tp + fp + fn) else None
        else:
            f1 = 2 * precision * recall / (precision + recall)
        if f1 is not None:
            f1s.append(f1)
        per_class[label] = {
            "precision": None if precision is None else round(precision, 4),
            "recall": None if recall is None else round(recall, 4),
            "f1": None if f1 is None else round(f1, 4),
            "support": tp + fn,
            "predicted": tp + fp,
            "correct": tp,
        }
    correct = sum(1 for gold, predicted in pairs if gold == predicted)
    total = len(pairs)
    return {
        "n_answered": total,
        "accuracy": round(correct / total, 4) if total else None,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "per_class": per_class,
        "confusion": matrix,
        "confusion_labels": list(labels),
        "confusion_axes": "rows = gold, columns = predicted",
    }


def brier_score(prob_rows: Sequence[Sequence[float]], gold: Sequence[int]) -> float | None:
    """Multiclass Brier: mean over rows of the summed squared error against the one-hot gold."""
    if not prob_rows:
        return None
    total = 0.0
    for probs, target in zip(prob_rows, gold):
        for index, p in enumerate(probs):
            want = 1.0 if index == int(target) else 0.0
            total += (float(p) - want) ** 2
    return round(total / len(prob_rows), 6)


def negative_log_likelihood(prob_rows: Sequence[Sequence[float]],
                            gold: Sequence[int]) -> float | None:
    if not prob_rows:
        return None
    total = 0.0
    for probs, target in zip(prob_rows, gold):
        total += -math.log(max(float(probs[int(target)]), 1e-12))
    return round(total / len(prob_rows), 6)


def expected_calibration_error(prob_rows: Sequence[Sequence[float]], gold: Sequence[int],
                               *, n_bins: int = 10) -> dict[str, Any] | None:
    """ECE over confidence bins, plus the bins themselves so the number can be inspected."""
    if not prob_rows:
        return None
    bins: list[dict[str, Any]] = []
    edges = [i / n_bins for i in range(n_bins + 1)]
    total = len(prob_rows)
    ece = 0.0
    for index in range(n_bins):
        lo, hi = edges[index], edges[index + 1]
        members = []
        for probs, target in zip(prob_rows, gold):
            confidence = max(float(p) for p in probs)
            in_bin = (lo < confidence <= hi) if index > 0 else (lo <= confidence <= hi)
            if in_bin:
                members.append((confidence, argmax(probs) == int(target)))
        if not members:
            bins.append({"lo": lo, "hi": hi, "count": 0, "mean_confidence": None,
                         "accuracy": None, "gap": None})
            continue
        mean_conf = sum(m[0] for m in members) / len(members)
        accuracy = sum(1 for m in members if m[1]) / len(members)
        gap = abs(mean_conf - accuracy)
        ece += (len(members) / total) * gap
        bins.append({"lo": round(lo, 4), "hi": round(hi, 4), "count": len(members),
                     "mean_confidence": round(mean_conf, 4), "accuracy": round(accuracy, 4),
                     "gap": round(gap, 4)})
    return {"ece": round(ece, 6), "n_bins": n_bins, "n_rows": total, "bins": bins,
            "definition": "|mean confidence - accuracy| weighted by bin population, answered rows only"}


def coverage_report(prob_rows: Sequence[Sequence[float]], gold: Sequence[int],
                    threshold: float) -> dict[str, Any]:
    """Abstention accounting: a row is answered only when its peak confidence reaches threshold."""
    if not prob_rows:
        return {"n_total": 0, "n_answered": 0, "n_abstained": 0, "coverage": None,
                "accuracy_on_answered": None, "threshold": float(threshold)}
    answered_correct = 0
    answered = 0
    for probs, target in zip(prob_rows, gold):
        if max(float(p) for p in probs) >= float(threshold):
            answered += 1
            answered_correct += 1 if argmax(probs) == int(target) else 0
    total = len(prob_rows)
    return {
        "threshold": round(float(threshold), 6),
        "n_total": total,
        "n_answered": answered,
        "n_abstained": total - answered,
        "coverage": round(answered / total, 4),
        "abstention_rate": round((total - answered) / total, 4),
        "accuracy_on_answered": round(answered_correct / answered, 4) if answered else None,
        "correct_on_answered": answered_correct,
    }


def choose_threshold(prob_rows: Sequence[Sequence[float]], gold: Sequence[int], *,
                     min_coverage: float = 0.6, step: float = 0.01) -> dict[str, Any]:
    """Freeze an abstention threshold from measured confidence, subject to a coverage floor.

    The objective is honest: highest accuracy among answered rows, among thresholds that keep
    at least ``min_coverage`` of the split. When no threshold meets the floor the strictest
    available coverage is reported instead, with ``floor_met`` false.
    """
    if not prob_rows:
        raise ValueError("choose_threshold needs at least one row")
    thresholds = [round(i * step, 6) for i in range(int(round(1.0 / step)) + 1)]
    scored = []
    for threshold in thresholds:
        report = coverage_report(prob_rows, gold, threshold)
        if report["n_answered"]:
            scored.append((report["accuracy_on_answered"], report["coverage"], threshold, report))
    if not scored:
        raise ValueError("no threshold answered any row")
    meeting = [s for s in scored if s[1] >= float(min_coverage)]
    floor_met = bool(meeting)
    pool = meeting or scored
    pool.sort(key=lambda s: (-s[0], s[2]))
    best = pool[0]
    return {**best[3], "min_coverage": float(min_coverage), "floor_met": floor_met,
            "objective": "max accuracy on answered rows subject to coverage floor; ties to the "
                         "lowest threshold",
            "thresholds_evaluated": len(thresholds)}


def latency_summary(values_ms: Sequence[float]) -> dict[str, Any]:
    """p50/p95 by nearest-rank on the measured samples (no interpolation, no smoothing)."""
    clean = sorted(float(v) for v in values_ms)
    if not clean:
        return {"n": 0, "p50_ms": None, "p95_ms": None}
    def rank(p: float) -> float:
        index = max(0, min(len(clean) - 1, math.ceil(p * len(clean)) - 1))
        return clean[index]
    return {"n": len(clean), "p50_ms": round(rank(0.5), 1), "p95_ms": round(rank(0.95), 1),
            "min_ms": round(clean[0], 1), "max_ms": round(clean[-1], 1),
            "mean_ms": round(sum(clean) / len(clean), 1)}


def evaluate_split(logits_rows: Sequence[LogitsRow], labels: Sequence[str], *,
                   temperature: float, threshold: float,
                   latencies_ms: Sequence[float] | None = None) -> dict[str, Any]:
    """Full held-out report for one temperature/threshold pair (frozen before the split is read)."""
    gold = [int(target) for _, target in logits_rows]
    raw_probs = [softmax(logits, 1.0) for logits, _ in logits_rows]
    cal_probs = [softmax(logits, temperature) for logits, _ in logits_rows]
    answered = [(probs, target) for probs, target in zip(cal_probs, gold)
                if max(probs) >= float(threshold)]
    out: dict[str, Any] = {
        "n": len(logits_rows),
        "labels": list(labels),
        "temperature": round(float(temperature), 6),
        "threshold": round(float(threshold), 6),
        "calibrated": coverage_report(cal_probs, gold, threshold),
        "raw_baseline": coverage_report(raw_probs, gold, threshold),
    }
    if answered:
        answered_probs = [p for p, _ in answered]
        answered_gold = [g for _, g in answered]
        pairs = [(g, argmax(p)) for p, g in zip(answered_probs, answered_gold)]
        out["calibrated"].update(classification_metrics(pairs, labels))
        out["calibrated"]["brier"] = brier_score(answered_probs, answered_gold)
        out["calibrated"]["nll"] = negative_log_likelihood(answered_probs, answered_gold)
        out["calibrated"]["calibration_error"] = expected_calibration_error(answered_probs,
                                                                           answered_gold)
        out["raw_baseline"]["brier"] = brier_score(answered_probs, answered_gold) if temperature == 1.0 else None
        out["raw_baseline"]["calibration_error"] = expected_calibration_error(answered_probs, answered_gold)
    else:
        out["calibrated"].update({"accuracy": None, "macro_f1": None, "per_class": {},
                                  "brier": None, "nll": None, "calibration_error": None,
                                  "note": "no row reached the frozen threshold"})
    # Raw reference metrics over every row, so the calibration change is visible even when the
    # frozen threshold abstains: same decisions, different probabilities.
    raw_pairs = [(g, argmax(p)) for p, g in zip(raw_probs, gold)]
    out["raw_full_coverage"] = {
        "accuracy": classification_metrics(raw_pairs, labels)["accuracy"],
        "macro_f1": classification_metrics(raw_pairs, labels)["macro_f1"],
        "brier": brier_score(raw_probs, gold),
        "nll": negative_log_likelihood(raw_probs, gold),
        "calibration_error": expected_calibration_error(raw_probs, gold),
    }
    cal_full_pairs = [(g, argmax(p)) for p, g in zip(cal_probs, gold)]
    out["calibrated_full_coverage"] = {
        "accuracy": classification_metrics(cal_full_pairs, labels)["accuracy"],
        "brier": brier_score(cal_probs, gold),
        "nll": negative_log_likelihood(cal_probs, gold),
        "calibration_error": expected_calibration_error(cal_probs, gold),
    }
    out["choice_unchanged_by_temperature"] = [argmax(p) for p in raw_probs] == [argmax(p) for p in cal_probs]
    if latencies_ms:
        out["latency_ms"] = latency_summary(latencies_ms)
    return out


__all__ = ["assert_choice_preserved", "argmax", "brier_score", "choose_threshold",
           "classification_metrics", "confusion_matrix", "coverage_report",
           "evaluate_split", "expected_calibration_error", "fit_temperature", "latency_summary",
           "mean_nll", "negative_log_likelihood", "softmax"]
