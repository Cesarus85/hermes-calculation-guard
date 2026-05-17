#!/usr/bin/env python3
"""Run a dependency-free smoke test against the Hermes Calculation Guard hook."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "calculation-guard" / "__init__.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("calculation_guard_plugin", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    guard = load_guard()
    prompts = [
        ("Rechne 77 / 18 * 100", "basic_arithmetic"),
        ("588 km Route, 77 kWh Batterie, Verbrauch 16-22 kWh/100 km", "ev_route"),
        ("153,51 Euro inklusive 19% MwSt netto herausrechnen", "finance_basic"),
        ("Wie weit komme ich in 2h bei 110 km/h?", "time_distance"),
    ]

    failures = []
    for prompt, expected_domain in prompts:
        result = guard.pre_llm_calculation_guard("smoke", prompt, "qwen3:latest", "ollama")
        domains = []
        if result and isinstance(result, dict):
            metadata = result.get("metadata") or {}
            decision = metadata.get("calculation_guard") or {}
            domains = decision.get("domains") or []
        ok = expected_domain in domains
        print(f"{'OK' if ok else 'FAIL'} {expected_domain}: {prompt}")
        if result:
            print(json.dumps({"domains": domains, "context_chars": len(result.get("context", ""))}, ensure_ascii=False))
        if not ok:
            failures.append({"prompt": prompt, "expected_domain": expected_domain, "domains": domains})

    status = json.loads(guard.calculation_guard_status({"limit": 5}))
    print(json.dumps({"plugin": status["plugin"], "version": status["version"], "decisions": len(status["decisions"])}, ensure_ascii=False))
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
