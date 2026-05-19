# Known Good Hermes Conversations

These transcripts are small, reproducible checks for a Hermes installation after updating Calculation Guard.

## Version And Status

Prompt:

```text
calculation_guard_status
```

Expected:

- version is `0.1.0-beta.6` or newer
- `status_version` is `2`
- `external_services_used` is `false`
- `summary.history.by_reason` and `summary.history.rule_flags` are present

## Basic Arithmetic Injection

Prompt:

```text
Rechne 77 / 18 * 100
```

Expected answer shape:

```text
427,78
```

Follow-up:

```text
calculation_guard_status
```

Expected diagnostics:

- latest or recent decision has `action: injected`
- domain includes `basic_arithmetic`
- visible effect is calculation context injection

## EV Energy Without Charge Window

Prompt:

```text
588 km Route, 77 kWh Batterie, Verbrauch 16-22 kWh/100 km
```

Expected answer shape:

- full battery range is `350-481 km`
- route energy need is `94-129 kWh`
- answer may say that intermediate charging is required or likely
- answer must not state a concrete stop count such as `ein Ladestopp`, `1-2 Stopps`, or `mindestens 1 Ladestopp`

Expected diagnostics:

- domain includes `ev_route`
- computed includes `mid_route_charging_required: true`
- computed includes `exact_stop_count_calculated: false`
- rule flags include `ev_no_exact_stop_count`

## EV Energy With Charge Window

Prompt:

```text
588 km Route, 77 kWh Batterie, Verbrauch 16-22 kWh/100 km, Ladefenster 20-80%
```

Expected answer shape:

- full battery range is `350-481 km`
- route energy need is `94-129 kWh`
- charge window energy is `46,2 kWh`
- `1-2` may be named only as a mathematical lower bound, not an exact route plan

Expected diagnostics:

- domain includes only `ev_route` for this calculation
- domain does not include `percentages` merely because of `20-80%`
- rule flags include `ev_charge_window_lower_bound`

## Finance And Unit Coverage

Prompts:

```text
Addiere 12,99 + 4,50 + 18 Euro
29,99 Euro pro Monat, was kostet das im Jahr?
Von 80 auf 100, wie viel Prozent mehr?
36 km/h in m/s
```

Expected answer shapes:

- `35,49 Euro`
- `359,88 Euro pro Jahr`
- `25%`
- `10 m/s`

Expected diagnostics:

- domains include `finance_basic`, `percentages`, and `unit_conversion` across the recent decisions

## Intercom Message Forwarding

Prompt:

```text
schicke eine Nachricht an Sibylle über Jarvis, sie soll mir folgende Rechnung beantworten: 1+1= ?
```

Expected behavior:

- Calculation Guard must not answer `1+1=2`
- Hermes/Ares should proceed with the Jarvis/Intercom/message workflow

Expected diagnostics:

- recent decision has `action: skipped`
- `reason` is `message-forwarding`
- rule flags include `message_forwarding_skip`

Manual override remains possible:

```text
/calculate schicke eine Nachricht an Sibylle über Jarvis mit 1+1= ?
```

