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

- [ ] Create `calculation-guard/plugin.yaml`.
- [ ] Create `calculation-guard/__init__.py`.
- [ ] Implement `pre_llm_call` hook.
- [ ] Return Hermes-compatible context injection.
- [ ] Add plugin version constant.
- [ ] Add README installation instructions.
- [ ] Add MIT license.
- [ ] Add dependency-free unit test structure.

## v0.2 - Model Gate And Manual Controls

Goal: match the Research Guard philosophy: primarily help local models, optionally cloud models.

- [ ] Add local model/provider detection.
- [ ] Add cloud model/provider detection.
- [ ] Default to `only_local=true`.
- [ ] Add `CALC_GUARD_ALLOW_CLOUD_TRIGGERS=false`.
- [ ] Add `/calculate` and `#calculate` manual force.
- [ ] Add `/no-calculate` and `#no-calculate` manual skip.
- [ ] Add decision reasons for local, cloud, forced, skipped, disabled.

## v0.3 - Safe Arithmetic Core

Goal: deterministic arithmetic without unsafe code execution.

- [ ] Add safe expression parser.
- [ ] Support `+`, `-`, `*`, `/`, parentheses, powers if safe.
- [ ] Support decimal comma and decimal point.
- [ ] Reject unsafe syntax.
- [ ] Add rounding policy.
- [ ] Add tests proving raw `eval` is not used.

## v0.4 - Percentages And Unit Conversion

Goal: cover common everyday calculation failures.

- [ ] Percent of value.
- [ ] Percentage increase/decrease.
- [ ] Discount.
- [ ] VAT/sales-tax style add/remove.
- [ ] Unit conversion for distance, mass, volume, time, power, and energy.
- [ ] Explicit ambiguity warnings for uncertain units.

## v0.5 - EV Route Plausibility

Goal: prevent obvious EV range and energy errors in local-model route answers.

- [ ] Parse distance in km.
- [ ] Parse battery capacity in kWh.
- [ ] Detect likely `kW battery` typo and warn.
- [ ] Parse consumption in kWh/100 km.
- [ ] Parse consumption ranges.
- [ ] Parse start SoC and reserve/target SoC when supplied.
- [ ] Compute full-battery range.
- [ ] Compute route energy need.
- [ ] Compute rough missing energy.
- [ ] Add guardrails: no exact charge time, no live availability, no optimized stop order.
- [ ] Add tests for the known 77 kWh / 16-22 kWh/100 km / 588 km scenario.

## v0.6 - Fuel Route Plausibility

Goal: support combustion vehicles and hybrid/fuel prompts.

- [ ] Parse consumption in l/100 km.
- [ ] Parse tank size in liters.
- [ ] Parse start tank percent.
- [ ] Compute full-tank range.
- [ ] Compute route fuel need.
- [ ] Compute rough missing fuel.
- [ ] Add guardrails: no live fuel price, no guaranteed station availability.

## v0.7 - Time, Distance, Speed

Goal: cover travel and planning math independent of Google APIs.

- [ ] Compute time from distance and speed.
- [ ] Compute speed from distance and time.
- [ ] Compute distance from speed and time.
- [ ] Support hours/minutes parsing.
- [ ] Warn when this is not a route planner and ignores traffic.

## v0.8 - Diagnostics And Status

Goal: make every calculation decision inspectable.

- [ ] Add in-memory decision ring buffer.
- [ ] Add `calculation_guard_status`.
- [ ] Add `calculation_guard_diagnostics`.
- [ ] Record detected domain, parsed inputs, computed outputs, warnings, model gate, and visible effect.
- [ ] Add prompt-preview redaction for diagnostics.
- [ ] Add skipped categories and explanations.

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
- [ ] Manual install instructions documented.
- [ ] Status diagnostics documented.
- [ ] At least 30 dependency-free tests.
- [ ] Known limitations documented.
- [ ] Release notes added.

## Explicit Non-Goals

- [ ] LIMIT No external calculation API calls.
- [ ] LIMIT No raw `eval`.
- [ ] LIMIT No hidden chain-of-thought generation.
- [ ] LIMIT No guarantee that local models obey injected context.
- [ ] LIMIT No exact EV charging optimizer without real segment, vehicle, charging-curve, and station data.
- [ ] LIMIT No regulated financial, tax, medical, or legal advice.

