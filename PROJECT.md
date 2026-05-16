# Hermes Calculation Guard Project Specification

This document is written for a fresh Codex session. It should contain enough context to implement the first beta without needing prior chat history.

## Product Goal

Build a Hermes Agent plugin that improves numerical reliability for local and small LLMs by injecting deterministic calculation results, unit interpretations, and plausibility warnings before the model answers.

The plugin should be to calculations what Hermes Research Guard is to external facts:

- Research Guard: "Do we need fresh/source-backed knowledge?"
- Calculation Guard: "Do we need deterministic arithmetic or unit checking?"

## Primary Users

- Hermes users running local models such as Qwen, Llama, Mistral, Gemma, Phi, DeepSeek, Ollama, LM Studio, vLLM, TGI, llama.cpp, MLX, or similar providers.
- Users who want local models to answer practical numeric questions more reliably.
- Users who already use Hermes Research Guard and want similar guardrails for calculations.

## Non-Goals

- Do not implement a general CAS/symbolic algebra system.
- Do not implement hidden chain-of-thought generation.
- Do not send prompts to external calculation APIs.
- Do not claim domain facts that were not provided.
- Do not turn rough calculations into exact predictions.
- Do not provide regulated financial, medical, or legal advice.
- Do not replace ABRP, Google Maps, vehicle apps, spreadsheet software, or professional calculators.

## Hermes Integration Requirements

The plugin should follow the Hermes Research Guard pattern where possible:

- Provide a `pre_llm_call` hook.
- Return injected context as `{"context": "..."}` or the Hermes-supported equivalent.
- Keep injection compact, explicit, and current-turn scoped.
- Avoid system-prompt assumptions because Hermes plugin context is injected into the current user turn.
- Keep diagnostics available through Hermes tools.

Expected plugin directory:

```text
calculation-guard/
  plugin.yaml
  __init__.py
  config.example.json
```

## Suggested Plugin Identity

- Plugin name: `calculation-guard`
- Repository: `Cesarus85/hermes-calculation-guard`
- Package title: `Hermes Calculation Guard`
- Runtime: Python, dependency-light
- License: MIT

## Configuration

Suggested environment variables:

| Variable | Default | Purpose |
|---|---:|---|
| `CALC_GUARD_ENABLED` | `true` | Master switch |
| `CALC_GUARD_ONLY_LOCAL` | `true` | Auto-trigger only for local/small models |
| `CALC_GUARD_ALLOW_CLOUD_TRIGGERS` | `false` | Allow automatic calculation context for cloud models |
| `CALC_GUARD_MODE` | `balanced` | `conservative`, `balanced`, or `aggressive` |
| `CALC_GUARD_MAX_CONTEXT_CHARS` | `3000` | Maximum injected context size |
| `CALC_GUARD_DECISION_HISTORY` | `30` | In-memory status buffer size |
| `CALC_GUARD_ENABLE_EV_ROUTE` | `true` | Enable EV route calculations |
| `CALC_GUARD_ENABLE_FUEL_ROUTE` | `true` | Enable fuel route calculations |
| `CALC_GUARD_ENABLE_FINANCE_BASIC` | `true` | Enable basic totals, discounts, percentages |
| `CALC_GUARD_ENABLE_UNIT_CONVERSION` | `true` | Enable local unit conversion |

Suggested persistent config file:

```text
~/.hermes/calculation-guard.json
```

Suggested tool:

```text
calculation_guard_config
```

Actions:

- `show`
- `set`
- `enable`
- `disable`
- `set_mode`
- `set_cloud_triggers`

## Model Gate

Default:

- local/small models: automatic triggers allowed
- cloud models: skipped unless manually forced or config enables cloud triggers

Local model/provider patterns should initially mirror Research Guard:

```text
qwen, ollama, llama, mistral, gemma, phi, deepseek, yi-, codellama, local,
lmstudio, lm-studio, mlx, gguf, vllm, tgi, kimi-k2, minimax-m2, goliath
```

Cloud patterns:

```text
openai, anthropic, gemini, google, openrouter, perplexity, gpt-, claude,
moonshot, kimi, minimax, synthetic, zai
```

Manual force and skip:

```text
#calculate ...
/calculate ...
#no-calculate ...
/no-calculate ...
```

## Trigger Classes

### Basic Arithmetic

Trigger examples:

```text
Was sind 19% von 349?
Rechne 77 / 18 * 100.
Addiere diese Beträge.
```

Output:

- expression parsed
- deterministic result
- rounding note

### Percentages

Supported:

- percent of value
- increase/decrease
- percentage difference
- discount
- VAT/sales tax style calculations

Examples:

```text
Was kostet 129 Euro mit 19% MwSt?
Wie viel sind 15% Rabatt auf 899 Euro?
```

### Unit Conversion

Start with conservative, common conversions:

- km, m, cm, mm
- kg, g
- l, ml
- h, min, s
- kW, W
- kWh, Wh
- km/h and m/s
- l/100 km and km/l where explicit

Do not overreach into ambiguous units without asking or warning.

### Time/Distance/Speed

Examples:

```text
Wie lange brauche ich für 588 km bei 110 km/h?
Welche Durchschnittsgeschwindigkeit sind 410 km in 4h 30min?
```

### EV Route Plausibility

Inputs:

- distance km
- battery kWh
- consumption kWh/100 km
- start SoC percent
- target/reserve SoC percent
- optionally charging window

Calculations:

- full-battery range
- usable start energy
- route energy need
- lower-bound missing energy
- lower-bound number of mid-route charges if charge window is provided

Warnings:

- `kW battery` likely means `kWh battery capacity`
- battery gross/net ambiguity
- no vehicle charge curve
- no weather/elevation/speed model
- no live charger availability

### Fuel Route Plausibility

Inputs:

- distance km
- consumption l/100 km
- tank size liters
- start tank percent
- reserve percent/liters

Calculations:

- full-tank range
- route fuel need
- usable start fuel
- missing fuel
- lower-bound refuel need

Warnings:

- no fuel price guarantee
- no live gas station availability
- no traffic/elevation/speed model

### Basic Finance

Start small:

- totals
- discounts
- VAT/sales tax
- monthly/yearly cost
- simple percentage change

Warnings:

- not financial advice
- no market prediction
- no tax/legal interpretation

## Calculation Context Contract

The injected context should be compact and explicit.

Example:

```text
[Calculation Guard]
Domain: ev_route
Confidence: high for arithmetic, medium for assumptions

Inputs detected:
- distance_km: 588
- battery_kwh: 77
- consumption_kwh_per_100km_range: 16-22

Computed deterministically:
- full_battery_range_km: 350-481
- route_energy_need_kwh: 94-129
- lower_bound_mid_route_energy_need_kwh: 17-52

Rules for the model:
- Use these computed values instead of recalculating them.
- Distinguish arithmetic facts from assumptions.
- Do not claim live availability, exact charging time, exact SoC curve, weather impact, or route optimization.
- If the user supplied `77 kW battery`, interpret it as likely `77 kWh battery capacity` and mention the correction.
```

## Diagnostics

Add tools:

```text
calculation_guard_status
calculation_guard_diagnostics
```

Status should include:

- plugin version
- enabled/config snapshot
- model gate decision
- last decisions
- detected domain
- inputs parsed
- computations made
- warnings
- visible effect
- skipped reasons

Decision categories:

- `calculated_and_injected`
- `checked_and_skipped`
- `manual_calculation`
- `failed`

## Parser Strategy

Start deterministic and conservative.

Do:

- regular expressions for common numeric patterns
- locale-aware decimal handling: `4,5` and `4.5`
- German and English unit aliases
- range parsing: `16-22`, `16 bis 22`, `16 to 22`
- explicit confidence for parsed values

Avoid initially:

- broad natural-language math parsing for complex expressions
- arbitrary code execution
- unsafe eval

For arithmetic expressions, use a safe parser:

- Python `ast` limited to numeric literals and arithmetic operators, or
- a small hand-written expression parser

Never use raw `eval`.

## Interaction With Research Guard

Calculation Guard should work independently, but it can benefit from Research Guard context when present.

Potential cooperation:

- Research Guard injects route distance from Google Routes.
- Calculation Guard parses that distance from recent context or decision status and computes EV/fuel plausibility.
- Research Guard remains responsible for source facts.
- Calculation Guard remains responsible for deterministic math.

Important boundary:

Calculation Guard should not fetch web data. It should not need API keys.

## Testing Requirements

Use dependency-free Python unit tests where possible.

Minimum tests for first beta:

- local/cloud model gate
- manual force and skip
- percentage calculations
- safe arithmetic parser
- decimal comma parsing
- EV range math
- EV `kW` vs `kWh` correction warning
- fuel range math
- time/distance/speed calculations
- no unsafe eval
- status diagnostics
- prompt redaction for diagnostics

## Suggested First Beta Acceptance Criteria

Version `0.1.0-beta.1` is acceptable when:

- Hermes can load the plugin.
- `pre_llm_call` injects calculation context for supported local-model prompts.
- cloud model auto-trigger is disabled by default.
- manual `/calculate` works.
- EV route math prevents obvious range/energy errors.
- `calculation_guard_status` shows useful diagnostics.
- tests pass without external services.

