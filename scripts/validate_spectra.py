#!/usr/bin/env python3
"""Validate real GZoltar spectrum files without creating scores/labels.

Some GZoltar builds append +/- to matrix.txt; other builds encode outcomes
in tests.csv. Both must agree when both are present.
"""
import argparse
import csv
import json
from pathlib import Path


def validate(directory: Path, candidate_file: Path):
    with (directory / "tests.csv").open(newline="", encoding="utf-8-sig") as f:
        raw_tests = list(csv.reader(f))
    with (directory / "spectra.csv").open(newline="", encoding="utf-8-sig") as f:
        raw_spec = list(csv.reader(f))
    if not raw_tests or not raw_spec:
        raise ValueError("Empty tests/spectra CSV")
    if raw_tests[0] and raw_tests[0][0].lower() == "name":
        raw_tests = raw_tests[1:]
    if raw_spec[0] and raw_spec[0][0].lower() == "name":
        raw_spec = raw_spec[1:]
    tests = [r[0].strip() for r in raw_tests if r]
    spectra = [r[0].strip() for r in raw_spec if r]
    if len(set(tests)) != len(tests):
        raise ValueError("Duplicate test names")
    if len(set(spectra)) != len(spectra):
        raise ValueError("Duplicate spectrum positions")
    if not tests or not spectra:
        raise ValueError("No tests/components")
    cand = {x.strip() for x in candidate_file.read_text(encoding="utf-8").splitlines() if x.strip()}
    if not cand:
        raise ValueError("No source-derived candidate classes")
    statuses = []
    nonzero = 0
    nr = 0
    with (directory / "matrix.txt").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                raise ValueError(f"Blank matrix row {nr+1}")
            toks = line.split()
            trailer = None
            if len(toks) == len(spectra) + 1 and toks[-1] in ("+", "-"):
                trailer = "PASS" if toks.pop() == "+" else "FAIL"
            if len(toks) != len(spectra) or any(t not in ("0", "1") for t in toks):
                raise ValueError(f"Malformed matrix row {nr+1}: {len(toks)} components, expected {len(spectra)}")
            nonzero += sum(t == "1" for t in toks)
            csv_status = None
            if nr < len(raw_tests) and len(raw_tests[nr]) >= 2:
                v = raw_tests[nr][1].strip().upper()
                if v in ("PASS", "PASSED", "+"):
                    csv_status = "PASS"
                elif v in ("FAIL", "FAILED", "ERROR", "-"):
                    csv_status = "FAIL"
            if csv_status and trailer and csv_status != trailer:
                raise ValueError(f"Test outcome mismatch at matrix row {nr+1}")
            statuses.append(csv_status or trailer)
            nr += 1
    if nr != len(tests):
        raise ValueError(f"Test/matrix count mismatch: {len(tests)} vs {nr}")
    if None in statuses:
        raise ValueError("Missing per-test PASS/FAIL outcomes")
    if "FAIL" not in statuses or "PASS" not in statuses:
        raise ValueError("Requires both passing and failing tests for Ochiai")
    if nonzero == 0:
        raise ValueError("Every coverage cell zero")
    unresolved = [s for s in spectra if "#" not in s or ":" not in s]
    return {
        "test_count": nr,
        "spectrum_positions": len(spectra),
        "candidate_buggy_production_classes": len(cand),
        "pass": statuses.count("PASS"),
        "fail": statuses.count("FAIL"),
        "one_cells": nonzero,
        "spectrum_positions_without_method_and_line": len(unresolved),
        "status": "INPUT_STRUCTURE_VALID" if not unresolved else "METHOD_MAPPING_INCOMPLETE",
        "not_checked": [
            "GZoltar instrumented exactly all candidate buggy-revision production classes",
            "test outcome equivalence with independent Defects4J test run",
            "method overloads / source method signature mapping",
            "held-out independently verified fault-method labels",
            "all original eligible tests were collected",
            "fair method-comparison protocol and baselines",
        ],
        "formal_E01_status": "BLOCKED_UNTIL_INDEPENDENT_AUDIT",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--candidate-file", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = validate(args.directory, args.candidate_file)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
