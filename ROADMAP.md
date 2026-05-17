# Hermes Calculation Guard Roadmap

Stand: 2026-05-16

## Legend

| Mark | Meaning |
|---|---|
| `[x]` | Done |
| `[ ]` | Planned |
| `[ ] ADAPT` | Needs adaptation to Hermes plugin behavior |
| `[ ] CHECK` | Needs validation against real Hermes runtime |
| `[ ] LIMIT` | Deliberate non-goal or known limitation |

## v0.1 - Hermes Plugin Scaffold

Goal: create a minimal Hermes plugin that can inject calculation context before local model answers.

- [x] Create `calculation-guard/plugin.yaml`.
- [x] Create `calculation-guard/__init__.py`.
- [x] Implement `pre_llm_call` hook.
- [x] Return Hermes-compatible context injection.
- [x] Add plugin version constant.
- [x] Add README installation instructions.
- [x] Add MIT license.
- [x] Add dependency-free unit test structure.

## v0.2 - Model Gate And Manual Controls

Goal: match the Research Guard philosophy: primarily help local models, optionally cloud models.

- [x] Add local model/provider detection.
- [x] Add cloud model/provider detection.
- [x] Default to `only_local=true`.
- [x] Add `CALC_GUARD_ALLOW_CLOUD_TRIGGERS=false`.
- [x] Add `/calculate` and `#calculate` manual force.
- [x] Add `/no-calculate` and `#no-calculate` manual skip.
- [x] Add decision reasons for local, cloud, forced, skipped, disabled.

## v0.3 - Safe Arithmetic Core

Goal: deterministic arithmetic without unsafe code execution.

- [x] Add safe expression parser.
- [x] Support `+`, `-`, `*`, `/`, parentheses, powers if safe.
- [x] Support decimal comma and decimal point.
- [x] Reject unsafe syntax.
- [x] Add rounding policy.
- [x] Add tests proving raw `eval` is not used.

## v0.4 - Percentages And Unit Conversion

Goal: cover common everyday calculation failures.

- [x] Percent of value.
- [x] Percentage increase/decrease.
- [x] Discount.
- [x] VAT/sales-tax style add/remove.
- [x] Unit conversion for distance, mass, volume, time, power, and energy.
- [x] Explicit ambiguity warnings for uncertain units.

## v0.5 - EV Route Plausibility

Goal: prevent obvious EV range and energy errors in local-model route answers.

- [x] Parse distance in km.
- [x] Parse battery capacity in kWh.
- [x] Detect likely `kW battery` typo and warn.
- [x] Parse consumption in kWh/100 km.
- [x] Parse consumption ranges.
- [x] Parse start SoC and reserve/target SoC when supplied.
- [x] Compute full-battery range.
- [x] Compute route energy need.
- [x] Compute rough missing energy.
- [x] Add guardrails: no exact charge time, no live availability, no optimized stop order.
- [x] Add tests for the known 77 kWh / 16-22 kWh/100 km / 588 km scenario.

## v0.6 - Fuel Route Plausibility

Goal: support combustion vehicles and hybrid/fuel prompts.

- [x] Parse consumption in l/100 km.
- [x] Parse tank size in liters.
- [x] Parse start tank percent.
- [x] Compute full-tank range.
- [x] Compute route fuel need.
- [x] Compute rough missing fuel.
- [x] Add guardrails: no live fuel price, no guaranteed station availability.

## v0.7 - Time, Distance, Speed

Goal: cover travel and planning math independent of Google APIs.

- [x] Compute time from distance and speed.
- [x] Compute speed from distance and time.
- [x] Compute distance from speed and time.
- [x] Support hours/minutes parsing.
- [x] Warn when this is not a route planner and ignores traffic.

## v0.8 - Diagnostics And Status

Goal: make every calculation decision inspectable.

- [x] Add in-memory decision ring buffer.
- [x] Add `calculation_guard_status`.
- [x] Add `calculation_guard_diagnostics`.
- [x] Record detected domain, parsed inputs, computed outputs, warnings, model gate, and visible effect.
- [x] Add prompt-preview redaction for diagnostics.
- [x] Add skipped categories and explanations.

## v0.9 - Research Guard Cooperation

Goal: allow both plugins to complement each other without tight coupling.

- [ ] CHECK Determine whether Hermes exposes previous plugin context to later plugins in a stable way.
- [ ] ADAPT Parse route distance from Research Guard route context when present.
- [ ] ADAPT Avoid duplicate EV math if Research Guard already injected equivalent values.
- [ ] ADAPT Define ordering expectations when both plugins are installed.
- [ ] Document recommended plugin order.

## v0.10 - Answer Consistency Linting

Goal: optionally catch contradictions after deterministic values are available.

- [ ] CHECK Determine whether Hermes exposes a post-answer hook or answer-rewrite hook.
- [ ] LIMIT If no post-answer hook exists, keep this as a future feature.
- [ ] Detect whether the model answer contradicts injected computed values.
- [ ] Detect mismatched units.
- [ ] Detect impossible percentages or negative values where not allowed.

## v1.0 - Beta Release Readiness

Goal: prepare a first useful public beta.

- [ ] README complete.
- [ ] PROJECT spec complete.
- [ ] Configuration documented.
- [x] Manual install instructions documented.
- [ ] Status diagnostics documented.
- [ ] At least 30 dependency-free tests.
- [ ] Known limitations documented.
- [x] Release notes added.

## Explicit Non-Goals

- [ ] LIMIT No external calculation API calls.
- [ ] LIMIT No raw `eval`.
- [ ] LIMIT No hidden chain-of-thought generation.
- [ ] LIMIT No guarantee that local models obey injected context.
- [ ] LIMIT No exact EV charging optimizer without real segment, vehicle, charging-curve, and station data.
- [ ] LIMIT No regulated financial, tax, medical, or legal advice.
