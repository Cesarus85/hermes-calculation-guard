# Release Notes

## 0.1.0-beta.6

- Expanded `calculation_guard_status` to status version 2 with reason summaries, rule flags, and history counters.
- Added rule-flag diagnostics for EV stop-count guardrails, charge-window lower bounds, manual controls, model gate skips, and message-forwarding skips.
- Added `docs/KNOWN_GOOD_CONVERSATIONS.md` with real Hermes verification prompts and expected diagnostics.

## 0.1.0-beta.5

- Added a message-forwarding guardrail so embedded calculations in Intercom/Jarvis/Sibylle/Ares delivery prompts are not answered by Calculation Guard.
- Kept `/calculate` as an explicit override even for forwarding-like prompts.

## 0.1.0-beta.4

- Tightened EV stop-count wording so models should not turn "charging required" into a concrete stop count without enough inputs.
- Clarified that charge-window stop counts are mathematical lower bounds, not exact route plans.
- Prevented EV charge windows such as `20-80%` from also triggering the generic percentage calculator.

## 0.1.0-beta.3

- Added stricter EV stop-count guardrails: without an explicit charge window, the guard injects energy facts but no computed stop count.
- Added EV charge-window parsing such as `Ladefenster 20-80%` and mathematical lower-bound mid-route charge counts when enough inputs are present.
- Added gross/net/usable battery basis detection and warnings for gross/brutto battery capacity.
- Added amount-list totals for simple currency sums.
- Added monthly-to-yearly and yearly-to-monthly cost calculations.
- Added percentage difference calculations for `von X auf Y` prompts.
- Added `km/h` to `m/s` speed unit conversion and reverse conversion.

## 0.1.0-beta.2

- Added a dependency-free smoke test script for local hook verification.
- Added percentage increase and decrease calculations.
- Added gross-to-net VAT removal calculations.
- Added distance-from-speed-and-time calculations.
- Added fuel route start tank, reserve, usable fuel, and minimum refuel math.
- Expanded README installation and verification guidance.

## 0.1.0-beta.1

- Added the first Hermes Calculation Guard beta implementation.
- Added `pre_llm_call` context injection for supported local/small-model prompts.
- Added default cloud-model auto-skip with manual `/calculate` override.
- Added safe arithmetic, percentage, unit conversion, EV route, fuel route, and time/distance calculations.
- Added status, diagnostics, config tools, and dependency-free unit tests.
