"""Eval runner — prints precision/recall table, per-reason-code accuracy, and stability."""
from __future__ import annotations
import argparse
import json
import logging
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from enforcer.core.clock import RealClock
from enforcer.core.config import Settings
from enforcer.core.schemas import Submission, ActivityType
from enforcer.core.validation import validate_observation, grounding_score as compute_gscore
from enforcer.agent.judge import judge, hash_image
from enforcer.llm.client import BedrockClient

log = logging.getLogger(__name__)

CASES_DIR = Path("evals/cases")


def load_cases(difficulty: str | None = None, case_id: str | None = None) -> list[dict]:
    cases = []
    for f in sorted(CASES_DIR.glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        if case_id and c["id"] != case_id:
            continue
        if difficulty and c.get("difficulty") != difficulty:
            continue
        cases.append(c)
    return cases


def run_case(case: dict, llm: BedrockClient, settings: Settings) -> dict:
    img_path = CASES_DIR / case.get("image", "")
    if img_path.exists():
        image_bytes = img_path.read_bytes()
    else:
        image_bytes = b"\xff\xd8\xff\xe0"

    sub = Submission(
        member_id=case.get("member_id", "eval_user"),
        guild_id="eval",
        submitted_at=case.get("submitted_at", "2026-09-10T12:00:00+05:30"),
        claimed_activity=ActivityType(case["claimed_activity"]),
        claimed_duration_min=case.get("claimed_duration_min"),
        claimed_distance_km=case.get("claimed_distance_km"),
        image_ref=case.get("image", "eval"),
        note=case.get("note"),
    )

    t0 = time.monotonic()
    v = judge(
        submission=sub,
        image_bytes=image_bytes,
        llm=llm,
        clock=RealClock(),
        known_hashes=set(),
        policy_path=settings.enforcer_policy_path,
    )
    latency = time.monotonic() - t0

    checks = validate_observation(v.observed)

    return {
        "id": case["id"],
        "expected_verdict": case["expected_verdict"],
        "actual_verdict": v.verdict,
        "expected_reason": case.get("expected_reason_code"),
        "actual_reason": v.reason_code.value if v.reason_code else None,
        "confidence": v.confidence,
        "grounding_score": v.grounding_score,
        "latency_s": latency,
        "grounding_ok": checks.ok,
        "difficulty": case.get("difficulty", "easy"),
        "correct": case["expected_verdict"] == v.verdict,
    }


def print_results(results: list[dict]) -> None:
    total = len(results)
    correct = sum(1 for r in results if r["expected_verdict"] == r["actual_verdict"])

    print(f"\n{'='*60}")
    print(f"  EVAL RESULTS — {total} cases")
    print(f"{'='*60}")
    print(f"  Overall accuracy:  {correct}/{total} ({correct/total:.0%})")

    # Precision/recall on ACCEPT
    tp = sum(1 for r in results if r["expected_verdict"] == "ACCEPT" and r["actual_verdict"] == "ACCEPT")
    fp = sum(1 for r in results if r["expected_verdict"] != "ACCEPT" and r["actual_verdict"] == "ACCEPT")
    fn = sum(1 for r in results if r["expected_verdict"] == "ACCEPT" and r["actual_verdict"] != "ACCEPT")
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    print(f"  ACCEPT precision:  {precision:.0%}")
    print(f"  ACCEPT recall:     {recall:.0%}")

    # Escalation rate
    escalated = sum(1 for r in results if r["actual_verdict"] == "ESCALATE")
    print(f"  Escalation rate:   {escalated}/{total} ({escalated/total:.0%})")

    # Grounding violations
    violations = sum(1 for r in results if not r["grounding_ok"])
    print(f"  Grounding issues:  {violations}/{total}")

    # Latency
    latencies = sorted(r["latency_s"] for r in results)
    if latencies:
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"  Latency p50/p95:   {p50:.1f}s / {p95:.1f}s")

    # Confusion matrix
    verdicts = ["ACCEPT", "REJECT", "ESCALATE"]
    print(f"\n  Confusion matrix (rows=expected, cols=actual):")
    print(f"  {'':>12} {'ACCEPT':>8} {'REJECT':>8} {'ESCALATE':>8}")
    for expected in verdicts:
        row = []
        for actual in verdicts:
            count = sum(1 for r in results if r["expected_verdict"] == expected and r["actual_verdict"] == actual)
            row.append(count)
        print(f"  {expected:>12} {row[0]:>8} {row[1]:>8} {row[2]:>8}")

    # Per-reason-code
    reason_results = defaultdict(lambda: {"correct": 0, "total": 0, "got_instead": Counter()})
    for r in results:
        if r["expected_reason"]:
            bucket = reason_results[r["expected_reason"]]
            bucket["total"] += 1
            if r["actual_reason"] == r["expected_reason"]:
                bucket["correct"] += 1
            elif r["actual_reason"]:
                bucket["got_instead"][r["actual_reason"]] += 1

    if reason_results:
        print(f"\n  Per-reason-code accuracy:")
        for code, data in sorted(reason_results.items()):
            acc = data["correct"] / data["total"] if data["total"] else 0
            print(f"    {code}: {data['correct']}/{data['total']} ({acc:.0%})")
            if data["got_instead"]:
                for alt, cnt in data["got_instead"].most_common(3):
                    print(f"      -> got {alt} instead: {cnt}")

    # 4c. Grounding score vs model confidence
    correct_results = [r for r in results if r.get("correct")]
    incorrect_results = [r for r in results if not r.get("correct")]
    if correct_results and incorrect_results:
        mean_gs_correct = sum(r["grounding_score"] for r in correct_results) / len(correct_results)
        mean_gs_incorrect = sum(r["grounding_score"] for r in incorrect_results) / len(incorrect_results)
        mean_conf_correct = sum(r["confidence"] for r in correct_results) / len(correct_results)
        mean_conf_incorrect = sum(r["confidence"] for r in incorrect_results) / len(incorrect_results)
        print(f"\n  Grounding score vs confidence (correct | incorrect):")
        print(f"    Grounding score: {mean_gs_correct:.3f} | {mean_gs_incorrect:.3f}  (delta {mean_gs_correct - mean_gs_incorrect:+.3f})")
        print(f"    Model confidence: {mean_conf_correct:.3f} | {mean_conf_incorrect:.3f}  (delta {mean_conf_correct - mean_conf_incorrect:+.3f})")
        gs_separates = abs(mean_gs_correct - mean_gs_incorrect) > 0.05
        conf_separates = abs(mean_conf_correct - mean_conf_incorrect) > 0.05
        if gs_separates and not conf_separates:
            print(f"    >> Grounding score separates correct/incorrect; model confidence does not.")
        elif not gs_separates and conf_separates:
            print(f"    >> Model confidence separates; grounding score does not.")
        elif gs_separates and conf_separates:
            print(f"    >> Both scores separate correct from incorrect verdicts.")
        else:
            print(f"    >> Neither score clearly separates correct from incorrect.")

    # By difficulty
    for diff in ["easy", "hard"]:
        subset = [r for r in results if r["difficulty"] == diff]
        if subset:
            c = sum(1 for r in subset if r["expected_verdict"] == r["actual_verdict"])
            print(f"\n  {diff.upper()} subset: {c}/{len(subset)} ({c/len(subset):.0%})")

    print(f"\n{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Run eval suite")
    parser.add_argument("--difficulty", choices=["easy", "hard"])
    parser.add_argument("--case", help="Run a single case by ID")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each case N times for stability")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    settings = Settings()
    llm = BedrockClient(settings.aws_region, settings.bedrock_vl_model_id, bearer_token=settings.aws_bearer_token_bedrock)

    cases = load_cases(args.difficulty, args.case)
    if not cases:
        print("No cases found.")
        sys.exit(1)

    print(f"Running {len(cases)} cases x {args.repeat} repeats...")

    all_results = []
    stability_data: dict[str, list[str]] = defaultdict(list)

    for case in cases:
        for rep in range(args.repeat):
            result = run_case(case, llm, settings)
            all_results.append(result)
            stability_data[case["id"]].append(result["actual_verdict"])
            if args.case:
                print(f"\n  Case {case['id']}:")
                print(f"    Expected: {result['expected_verdict']} ({result.get('expected_reason', '-')})")
                print(f"    Actual:   {result['actual_verdict']} ({result.get('actual_reason', '-')})")
                print(f"    Grounding score: {result['grounding_score']:.3f}")
                print(f"    Confidence:      {result['confidence']:.3f}")
                print(f"    Latency:         {result['latency_s']:.2f}s")
                print(f"    Grounding:       {'OK' if result['grounding_ok'] else 'VIOLATION'}")

    # For repeat=1, just show normal results
    if args.repeat == 1:
        print_results(all_results)
    else:
        # Show stability
        print_results(all_results)
        stable = sum(1 for verdicts in stability_data.values() if len(set(verdicts)) == 1)
        print(f"\n  Verdict stability: {stable}/{len(stability_data)} cases "
              f"({stable/len(stability_data):.0%}) stable across {args.repeat} runs")
        for cid, verdicts in stability_data.items():
            if len(set(verdicts)) > 1:
                print(f"    UNSTABLE: {cid} -> {verdicts}")


if __name__ == "__main__":
    main()
