from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "calculation-guard" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("calculation_guard_plugin", MODULE_PATH)
guard = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(guard)


class CalculationGuardTests(unittest.TestCase):
    def test_manual_calculate_prefixes_are_consistent(self):
        self.assertEqual(guard._should_calculate("#calculate 77 / 18 * 100"), (True, "explicit"))
        self.assertEqual(guard._should_calculate("/calculate 77 / 18 * 100"), (True, "explicit"))
        self.assertEqual(guard._should_calculate("#no-calculate 77 / 18 * 100"), (False, "opt-out"))
        self.assertEqual(guard._should_calculate("/no-calculate 77 / 18 * 100"), (False, "opt-out"))

    def test_slash_commands_are_skipped_unless_manual_calculate(self):
        self.assertEqual(guard._should_calculate("/status"), (False, "slash-command"))
        self.assertEqual(guard._should_calculate("/help"), (False, "slash-command"))

    def test_model_gate_recognizes_local_and_cloud_models(self):
        self.assertTrue(guard._is_local_or_small_model("qwen3:latest", "ollama"))
        self.assertTrue(guard._is_local_or_small_model("llama-3", "vllm"))
        self.assertFalse(guard._is_local_or_small_model("llama3:cloud", "ollama"))
        self.assertFalse(guard._is_local_or_small_model("gpt-5.2", "openai"))
        self.assertFalse(guard._should_skip_for_model_gate("gpt-5.2", "openai", True, "explicit"))

    def test_safe_arithmetic_parser(self):
        self.assertAlmostEqual(guard._safe_eval_expression("77 / 18 * 100"), 427.7777777, places=6)
        self.assertEqual(guard._round_value(guard._safe_eval_expression("2^3 + 1")), 9)
        with self.assertRaises(Exception):
            guard._safe_eval_expression("__import__('os').system('echo nope')")

    def test_decimal_comma_arithmetic(self):
        result = guard._calculate_arithmetic("Rechne 4,5 * 2")
        self.assertIsNotNone(result)
        self.assertEqual(result["computed"]["result"], 9)

    def test_percentages_and_discount(self):
        percent = guard._calculate_percentages("Was sind 19% von 349?")
        self.assertEqual(percent["computed"]["percent_of_value"], 66.31)

        discount = guard._calculate_percentages("15% Rabatt auf 899 Euro")
        self.assertEqual(discount["computed"]["discount_amount"], 134.85)
        self.assertEqual(discount["computed"]["discounted_value"], 764.15)

    def test_vat_calculation(self):
        vat = guard._calculate_percentages("129 Euro mit 19% MwSt")
        self.assertEqual(vat["domain"], "finance_basic")
        self.assertEqual(vat["computed"]["tax_amount"], 24.51)
        self.assertEqual(vat["computed"]["gross_value"], 153.51)

    def test_percentage_increase_and_decrease(self):
        increase = guard._calculate_percentages("349 plus 19%")
        self.assertEqual(increase["computed"]["change_amount"], 66.31)
        self.assertEqual(increase["computed"]["increased_value"], 415.31)

        decrease = guard._calculate_percentages("899 minus 15%")
        self.assertEqual(decrease["computed"]["change_amount"], 134.85)
        self.assertEqual(decrease["computed"]["decreased_value"], 764.15)

    def test_percentage_difference(self):
        result = guard._calculate_percentages("Von 80 auf 100, wie viel Prozent mehr?")
        self.assertEqual(result["computed"]["absolute_change"], 20)
        self.assertEqual(result["computed"]["percentage_change"], 25)

    def test_vat_remove_calculation(self):
        vat = guard._calculate_percentages("153,51 Euro inklusive 19% MwSt netto herausrechnen")
        self.assertEqual(vat["computed"]["net_value"], 129)
        self.assertEqual(vat["computed"]["tax_amount"], 24.51)

    def test_finance_amount_list_and_period_costs(self):
        total = guard._calculate_finance_basic("Addiere 12,99 + 4,50 + 18 Euro")
        self.assertEqual(total["computed"]["total"], 35.49)
        self.assertEqual(
            [item["domain"] for item in guard._calculate_all("Addiere 12,99 + 4,50 + 18 Euro")],
            ["finance_basic"],
        )

        yearly = guard._calculate_finance_basic("29,99 Euro pro Monat, was kostet das im Jahr?")
        self.assertEqual(yearly["computed"]["yearly_value"], 359.88)

        monthly = guard._calculate_finance_basic("360 Euro pro Jahr, was ist das pro Monat?")
        self.assertEqual(monthly["computed"]["monthly_value"], 30)

    def test_unit_conversion(self):
        conversion = guard._calculate_unit_conversion("Konvertiere 1,5 km in m")
        self.assertEqual(conversion["computed"]["converted_value"], 1500)
        self.assertIsNone(guard._calculate_unit_conversion("Konvertiere 5 km in kg")["computed"].get("converted_value"))

        speed = guard._calculate_unit_conversion("36 km/h in m/s")
        self.assertEqual(speed["computed"]["converted_value"], 10)

        reverse_speed = guard._calculate_unit_conversion("10 m/s in km/h")
        self.assertEqual(reverse_speed["computed"]["converted_value"], 36)

    def test_ev_route_math_known_scenario(self):
        result = guard._calculate_ev_route("588 km Route, 77 kWh Batterie, Verbrauch 16-22 kWh/100 km")
        self.assertEqual(result["domain"], "ev_route")
        self.assertEqual(result["computed"]["full_battery_range_km"], [350, 481])
        self.assertEqual(result["computed"]["route_energy_need_kwh"], [94, 129])
        self.assertNotIn("minimum_mid_route_charges_lower_bound", result["computed"])
        self.assertTrue(result["computed"]["mid_route_charging_required"])
        self.assertIn("exact charge-stop count", " ".join(result["warnings"]))

    def test_ev_charge_window_enables_stop_lower_bound(self):
        result = guard._calculate_ev_route("588 km Route, 77 kWh Batterie, Verbrauch 16-22 kWh/100 km, Ladefenster 20-80%")
        self.assertEqual(result["inputs"]["charge_window_percent"], [20, 80])
        self.assertEqual(result["computed"]["charge_window_energy_kwh"], 46.2)
        self.assertEqual(result["computed"]["minimum_mid_route_charges_lower_bound"], [1, 2])

    def test_ev_battery_basis_warnings(self):
        gross = guard._calculate_ev_route("588 km Route, 77 kWh brutto Batterie, Verbrauch 18 kWh/100 km")
        self.assertEqual(gross["inputs"]["battery_capacity_basis"], "gross")
        self.assertIn("Gross", " ".join(gross["warnings"]))

        usable = guard._calculate_ev_route("588 km Route, 77 kWh netto Batterie, Verbrauch 18 kWh/100 km")
        self.assertEqual(usable["inputs"]["battery_capacity_basis"], "usable")

    def test_ev_kw_battery_warning(self):
        result = guard._calculate_ev_route("588 km mit 77 kW Batterie und 18 kWh/100 km Verbrauch")
        self.assertIn("kW", " ".join(result["warnings"]))
        self.assertEqual(result["inputs"]["battery_kwh"], 77)

    def test_fuel_route_math(self):
        result = guard._calculate_fuel_route("600 km Strecke, 50 Liter Tank, Verbrauch 6 l/100 km")
        self.assertEqual(result["computed"]["full_tank_range_km"], [833.33, 833.33])
        self.assertEqual(result["computed"]["route_fuel_need_liters"], [36, 36])

    def test_fuel_route_start_tank_and_reserve(self):
        result = guard._calculate_fuel_route("600 km Strecke, 50 Liter Tank, Start Tank 80%, Reserve 10%, Verbrauch 6 l/100 km")
        self.assertEqual(result["inputs"]["start_tank_percent"], 80)
        self.assertEqual(result["inputs"]["reserve_percent"], 10)
        self.assertEqual(result["computed"]["usable_start_fuel_liters"], 35)
        self.assertEqual(result["computed"]["minimum_refuel_need_liters"], [1, 1])

    def test_time_distance_math(self):
        duration = guard._calculate_time_distance("Wie lange brauche ich für 588 km bei 110 km/h?")
        self.assertEqual(duration["computed"]["duration_minutes"], 320.73)

        speed = guard._calculate_time_distance("Welche Durchschnittsgeschwindigkeit sind 410 km in 4h 30min?")
        self.assertEqual(speed["computed"]["average_speed_kmh"], 91.11)

        distance = guard._calculate_time_distance("Wie weit komme ich in 2h bei 110 km/h?")
        self.assertEqual(distance["computed"]["distance_km"], 220)

    def test_pre_hook_injects_for_local_model_and_skips_cloud_auto(self):
        guard.DECISIONS.clear()
        response = guard.pre_llm_calculation_guard("s1", "Rechne 77 / 18 * 100", "qwen3", "ollama")
        self.assertIsInstance(response, dict)
        self.assertIn("[Calculation Guard: Kontext]", response["context"])
        self.assertEqual(guard.DECISIONS[-1]["action"], "injected")

        response = guard.pre_llm_calculation_guard("s1", "Rechne 77 / 18 * 100", "gpt-5.2", "openai")
        self.assertIsNone(response)
        self.assertEqual(guard.DECISIONS[-1]["reason"], "model-gate-cloud")

    def test_status_tool_reports_recent_decisions(self):
        guard.DECISIONS.clear()
        guard._record_decision("skipped", "no-supported-calculation", model="qwen")
        payload = json.loads(guard.calculation_guard_status({"limit": 1}))
        self.assertEqual(payload["plugin"], "calculation-guard")
        self.assertEqual(payload["version"], guard.__version__)
        self.assertEqual(payload["decisions"][0]["category"], "checked_and_skipped")
        self.assertFalse(payload["external_services_used"])

    def test_prompt_redaction_for_diagnostics(self):
        guard.DECISIONS.clear()
        guard._record_decision("skipped", "no-trigger", prompt="Mail test@example.com Token abcdefghijklmnopqrstuvwxyz1234567890 Telefon +49 123 456789")
        decision = json.loads(guard.calculation_guard_status({"limit": 1}))["decisions"][0]
        self.assertIn("[redacted-email]", decision["prompt_preview"])
        self.assertIn("[redacted-token]", decision["prompt_preview"])
        self.assertIn("[redacted-phone]", decision["prompt_preview"])


if __name__ == "__main__":
    unittest.main()
