# Hermes Calculation Guard

Hermes Calculation Guard is a planned Hermes Agent plugin for improving the numerical reliability of local and small language models.

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

Suggested config:

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

## Installation Goal

This repository is intended to become a Hermes Agent plugin. Like Hermes Research Guard, it should not be a standalone application.

Planned installation paths:

1. Hermes-initiated installation from GitHub.
2. Manual command-line installation into the Hermes plugin directory.

## Development Status

Planning scaffold only. See [PROJECT.md](PROJECT.md) and [ROADMAP.md](ROADMAP.md).

