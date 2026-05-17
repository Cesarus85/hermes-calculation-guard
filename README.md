# Hermes Calculation Guard

Hermes Calculation Guard is a Hermes Agent plugin for improving the numerical reliability of local and small language models.

It is intended to complement [Hermes Research Guard](https://github.com/Cesarus85/hermes-research-guard):

- Research Guard improves freshness and source grounding.
- Calculation Guard improves deterministic arithmetic, unit handling, and numerical plausibility.

The plugin should primarily run for local/small models such as Qwen, Llama, Mistral, Gemma, Phi, Ollama-hosted models, LM Studio, vLLM, TGI, llama.cpp, MLX, and similar providers. Optional cloud-model support should be available through configuration, but disabled by default.

## Problem

Small LLMs can often explain mathematical relationships correctly, but they are not reliable calculators. They may know the right formula and still produce wrong values, mix units, overstate precision, or contradict themselves later in the answer.

Example:

```text
Input:
77 kWh battery, 18 kWh/100 km consumption

Correct:
77 / 18 * 100 = 427 km

Typical failure:
125-135 km
```

This is not missing world knowledge. It is an execution problem: arithmetic, unit conversion, rounding, and consistency should be handled by deterministic code rather than by the model.

## Core Idea

Calculation Guard should inspect the user prompt and recent injected context before the LLM answers. If it detects a supported numerical task, it computes deterministic helper values and injects a compact calculation context into the current Hermes turn.

The model should explain the results, but it should not redo the core arithmetic from scratch.

Example injected context:

```json
{
  "calculation_guard": {
    "domain": "ev_route",
    "inputs": {
      "distance_km": 588,
      "battery_kwh": 77,
      "consumption_kwh_per_100km_range": [16, 22]
    },
    "computed": {
      "full_battery_range_km": [350, 481],
      "route_energy_need_kwh": [94, 129],
      "minimum_mid_route_energy_kwh": [17, 52]
    },
    "assumptions": [
      "consumption range is an explicit or conservative estimate",
      "usable battery was treated as 77 kWh because no usable/net capacity was supplied"
    ],
    "warnings": [
      "This is arithmetic support, not a live route or charging optimizer",
      "No charging curve, weather, speed, or elevation model was calculated"
    ]
  }
}
```

## Scope

Calculation Guard should be deterministic and transparent.

It should handle:

- arithmetic expressions
- percentages
- unit conversion
- range and interval math
- simple financial totals
- time/distance/speed calculations
- EV route plausibility math
- fuel route plausibility math
- consistency checks for numbers already present in a draft or context

It should not become:

- a symbolic math system
- a theorem prover
- a route optimizer
- a tax/legal/financial advice engine
- a hidden reasoning chain generator
- a replacement for domain-specific APIs

## First Target Domain: EV And Route Math

This is the strongest first use case because Hermes Research Guard already provides Google Routes/Places context.

Supported calculations:

- `range_km = battery_kwh / consumption_kwh_per_100km * 100`
- `route_energy_kwh = distance_km * consumption_kwh_per_100km / 100`
- usable energy from state of charge:
  - `usable_kwh = battery_kwh * (start_soc_percent - reserve_soc_percent) / 100`
- rough minimum charging need:
  - `missing_energy_kwh = max(0, route_energy_kwh - usable_start_energy_kwh)`
- lower-bound stop count when a max useful charge window is provided

Important boundary:

Calculation Guard may say what follows from assumptions. It must not claim the assumptions are real-world facts unless supplied by the user or a trusted upstream context.

Good:

```text
If we calculate with 18-22 kWh/100 km, the 588 km route needs roughly 106-129 kWh.
```

Bad:

```text
The VW ID.7 will consume exactly 18 kWh/100 km on this route.
```

## Model Gate

Default behavior:

- run automatically for local/small models
- skip automatic injection for cloud models
- allow manual force
- allow optional cloud-model triggering through config

Config example:

```json
{
  "enabled": true,
  "only_local": true,
  "allow_cloud_calculation_triggers": false,
  "mode": "balanced",
  "max_context_chars": 3000,
  "domains": {
    "basic_arithmetic": true,
    "unit_conversion": true,
    "ev_route": true,
    "fuel_route": true,
    "finance_basic": true,
    "time_distance": true
  }
}
```

## Privacy

Calculation Guard does not need external web access for its core job. It should not send prompts to third-party services.

All supported calculations should run locally inside the Hermes plugin process.

## Current Beta Features

Version `0.1.0-beta.2` includes:

- `pre_llm_call` context injection for supported local/small-model prompts
- default cloud-model auto-skip with manual `/calculate` and `#calculate` override
- manual `/no-calculate` and `#no-calculate` opt-out
- safe arithmetic parser based on restricted Python AST nodes, not raw `eval`
- percentage, VAT add/remove, discount, percentage increase/decrease, and common unit conversions
- EV range and route energy plausibility math
- fuel range and route fuel plausibility math
- time/distance/speed calculations, including distance from speed and duration
- `calculation_guard_status`, `calculation_guard_diagnostics`, and `calculation_guard_config`
- in-memory decision diagnostics with prompt-preview redaction

## Installation

This repository is intended to be installed like Hermes Research Guard. It is not a standalone application.

Expected plugin directory:

```text
calculation-guard/
  plugin.yaml
  __init__.py
  config.example.json
```

### Install From GitHub

Use this after the version you want to test has been pushed:

```text
Repository: https://github.com/Cesarus85/hermes-calculation-guard
Plugin directory inside repository: calculation-guard/
```

Tell Hermes:

```text
Install the Hermes plugin from https://github.com/Cesarus85/hermes-calculation-guard.
Use the plugin directory calculation-guard/.
Load plugin.yaml, register the pre_llm_call hook from __init__.py, and enable calculation_guard_status, calculation_guard_diagnostics, and calculation_guard_config.
```

### Install From Local Checkout

For local testing before a release:

```text
/Users/irisclawbot/Documents/Hermes Plugins/hermes-calculation-guard/calculation-guard
```

Tell Hermes:

```text
Install or link this local Hermes plugin directory:
/Users/irisclawbot/Documents/Hermes Plugins/hermes-calculation-guard/calculation-guard

After loading it, test:
1. Rechne 77 / 18 * 100
2. 588 km Route, 77 kWh Batterie, Verbrauch 16-22 kWh/100 km
3. 153,51 Euro inklusive 19% MwSt netto herausrechnen
4. calculation_guard_status
```

Expected behavior:

- local/small models get automatic calculation context for supported prompts
- cloud models skip automatic injection by default
- `/calculate ...` forces calculation even when the model gate would skip
- `/no-calculate ...` skips calculation for the current turn

## Local Verification

Run the dependency-free unit tests from the repository root:

```bash
python3 -m unittest discover -s test
```

Run the smoke test to exercise the hook directly without a full Hermes runtime:

```bash
python3 scripts/smoke_test.py
```

## Development Status

First beta implementation. See [PROJECT.md](PROJECT.md) and [ROADMAP.md](ROADMAP.md) for the remaining roadmap.
