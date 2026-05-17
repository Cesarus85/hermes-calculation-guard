"""Calculation Guard plugin for Hermes.

This plugin detects practical numerical tasks before a Hermes LLM call, runs
small deterministic calculations locally, and injects compact context for the
current turn. It mirrors the Research Guard integration style while staying
offline and dependency-free.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any


__version__ = "0.1.0-beta.1"
CONFIG_PATH = Path.home() / ".hermes" / "calculation-guard.json"
PLUGIN_CONFIG_PATH = Path(__file__).resolve().with_name("config.json")
MAX_DECISIONS = 30
DECISIONS: list[dict[str, Any]] = []

DEFAULT_LOCAL_MODEL_PATTERNS = (
    "qwen", "ollama", "llama", "mistral", "gemma", "phi", "deepseek",
    "yi-", "codellama", "local", "lmstudio", "lm-studio", "mlx", "gguf",
    "vllm", "tgi", "kimi-k2", "minimax-m2",
)
LOCAL_PROVIDER_PATTERNS = (
    "ollama", "lmstudio", "lm-studio", "mlx", "llama.cpp", "local",
    "vllm", "tgi", "goliath",
)
CLOUD_PROVIDER_PATTERNS = (
    "openai", "openai-codex", "anthropic", "gemini", "google", "openrouter",
    "perplexity", "moonshot", "kimi", "minimax", "synthetic", "zai",
)
CLOUD_MODEL_PATTERNS = (
    "gpt-", "claude", "sonnet", "opus", "haiku", "gemini", "openrouter",
    "anthropic", "openai", "moonshot", "perplexity",
)
EXPLICIT_CLOUD_MODEL_MARKERS = (":cloud",)

CALCULATE_PREFIX_RE = re.compile(r"^\s*(?:#|/)calculate\b\s*", re.IGNORECASE)
NO_CALCULATE_PREFIX_RE = re.compile(r"^\s*(?:#|/)no-calculate\b\s*", re.IGNORECASE)
SLASH_COMMAND_RE = re.compile(r"^\s*/(?!calculate\b|no-calculate\b)\S+", re.IGNORECASE)
STATUS_REQUEST_RE = re.compile(
    r"\b(?:calculation[-_\s]*guard|calculation_guard|calc[-_\s]*guard)\b[\s\S]{0,80}"
    r"\b(?:status|diagnos(?:e|tik|tic|tics)?|debug|zustand|health)\b"
    r"|"
    r"\b(?:status|diagnos(?:e|tik|tic|tics)?|debug|zustand|health)\b[\s\S]{0,80}"
    r"\b(?:calculation[-_\s]*guard|calculation_guard|calc[-_\s]*guard)\b"
    r"|"
    r"\bcalculation_guard_(?:status|diagnostics)\b",
    re.IGNORECASE,
)
CALC_WORD_RE = re.compile(
    r"\b(rechne|berechne|calculate|calculator|wieviel|wie viel|summe|addiere|"
    r"subtract|multipliziere|teile|prozent|percent|mwst|umsatzsteuer|rabatt|"
    r"discount|umrechnen|konvertiere|convert|reichweite|verbrauch|akku|batterie|"
    r"kwh|l/100\s*km|liter|tank|geschwindigkeit|tempo|durchschnittsgeschwindigkeit)\b",
    re.IGNORECASE,
)
NUMBER_RE = r"[-+]?\d+(?:[.,]\d+)?"

UNIT_ALIASES = {
    "km": ("distance", 1000.0),
    "kilometer": ("distance", 1000.0),
    "kilometern": ("distance", 1000.0),
    "m": ("distance", 1.0),
    "meter": ("distance", 1.0),
    "cm": ("distance", 0.01),
    "zentimeter": ("distance", 0.01),
    "mm": ("distance", 0.001),
    "kg": ("mass", 1000.0),
    "kilogramm": ("mass", 1000.0),
    "g": ("mass", 1.0),
    "gramm": ("mass", 1.0),
    "l": ("volume", 1.0),
    "liter": ("volume", 1.0),
    "ml": ("volume", 0.001),
    "milliliter": ("volume", 0.001),
    "h": ("time", 3600.0),
    "std": ("time", 3600.0),
    "stunde": ("time", 3600.0),
    "stunden": ("time", 3600.0),
    "min": ("time", 60.0),
    "minute": ("time", 60.0),
    "minuten": ("time", 60.0),
    "s": ("time", 1.0),
    "sekunde": ("time", 1.0),
    "sekunden": ("time", 1.0),
    "kw": ("power", 1000.0),
    "w": ("power", 1.0),
    "kwh": ("energy", 1000.0),
    "wh": ("energy", 1.0),
}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(name, str(default)))))
    except Exception:
        return default


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    return value if value in allowed else default


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def _plugin_config() -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "only_local": True,
        "allow_cloud_calculation_triggers": False,
        "mode": "balanced",
        "max_context_chars": 3000,
        "decision_history": MAX_DECISIONS,
        "domains": {
            "basic_arithmetic": True,
            "percentages": True,
            "unit_conversion": True,
            "ev_route": True,
            "fuel_route": True,
            "finance_basic": True,
            "time_distance": True,
        },
    }
    config = _merge_config(defaults, _read_json_file(PLUGIN_CONFIG_PATH))
    return _merge_config(config, _read_json_file(CONFIG_PATH))


def _config_bool(config: dict[str, Any], key: str, env_name: str, default: bool) -> bool:
    value = config.get(key, default)
    if env_name in os.environ:
        return _env_bool(env_name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _domain_enabled(config: dict[str, Any], domain: str, env_name: str, default: bool = True) -> bool:
    domains = config.get("domains") if isinstance(config.get("domains"), dict) else {}
    if env_name in os.environ:
        return _env_bool(env_name, default)
    value = domains.get(domain, default)
    return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _max_context_chars(config: dict[str, Any]) -> int:
    if "CALC_GUARD_MAX_CONTEXT_CHARS" in os.environ:
        return _env_int("CALC_GUARD_MAX_CONTEXT_CHARS", 3000, 800, 12000)
    try:
        return max(800, min(12000, int(config.get("max_context_chars", 3000))))
    except Exception:
        return 3000


def _config_snapshot() -> dict[str, Any]:
    config = _plugin_config()
    return {
        "enabled": _config_bool(config, "enabled", "CALC_GUARD_ENABLED", True),
        "only_local": _config_bool(config, "only_local", "CALC_GUARD_ONLY_LOCAL", True),
        "allow_cloud_calculation_triggers": _config_bool(
            config,
            "allow_cloud_calculation_triggers",
            "CALC_GUARD_ALLOW_CLOUD_TRIGGERS",
            False,
        ),
        "mode": _env_choice("CALC_GUARD_MODE", str(config.get("mode", "balanced")), {"conservative", "balanced", "aggressive"}),
        "max_context_chars": _max_context_chars(config),
        "decision_history": _env_int("CALC_GUARD_DECISION_HISTORY", int(config.get("decision_history", MAX_DECISIONS)), 5, 200),
        "domains": {
            "basic_arithmetic": _domain_enabled(config, "basic_arithmetic", "CALC_GUARD_ENABLE_BASIC_ARITHMETIC"),
            "percentages": _domain_enabled(config, "percentages", "CALC_GUARD_ENABLE_PERCENTAGES"),
            "unit_conversion": _domain_enabled(config, "unit_conversion", "CALC_GUARD_ENABLE_UNIT_CONVERSION"),
            "ev_route": _domain_enabled(config, "ev_route", "CALC_GUARD_ENABLE_EV_ROUTE"),
            "fuel_route": _domain_enabled(config, "fuel_route", "CALC_GUARD_ENABLE_FUEL_ROUTE"),
            "finance_basic": _domain_enabled(config, "finance_basic", "CALC_GUARD_ENABLE_FINANCE_BASIC"),
            "time_distance": _domain_enabled(config, "time_distance", "CALC_GUARD_ENABLE_TIME_DISTANCE"),
        },
        "config_path": str(CONFIG_PATH),
        "plugin_config_path": str(PLUGIN_CONFIG_PATH),
        "config_file_present": CONFIG_PATH.exists() or PLUGIN_CONFIG_PATH.exists(),
    }


def _is_local_or_small_model(model: str | None, provider: str | None = None) -> bool:
    model_l = (model or "").strip().lower()
    provider_l = (provider or "").strip().lower()
    if any(marker in model_l for marker in EXPLICIT_CLOUD_MODEL_MARKERS):
        return False
    if any(pattern in provider_l for pattern in CLOUD_PROVIDER_PATTERNS):
        return False
    if any(pattern in model_l for pattern in CLOUD_MODEL_PATTERNS):
        return False
    return any(pattern in model_l for pattern in DEFAULT_LOCAL_MODEL_PATTERNS) or any(
        pattern in provider_l for pattern in LOCAL_PROVIDER_PATTERNS
    )


def _should_skip_for_model_gate(model: str | None, provider: str | None, should_calculate: bool, reason: str) -> bool:
    if not should_calculate or reason == "explicit":
        return False
    config = _config_snapshot()
    if not config["only_local"]:
        return False
    if config["allow_cloud_calculation_triggers"]:
        return False
    return not _is_local_or_small_model(model, provider)


def _message_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        return _message_text(message.get("content"))
    if isinstance(message, list):
        parts = []
        for item in message:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(_message_text(item))
        return "\n".join(part for part in parts if part)
    return "" if message is None else str(message)


def _strip_control_prefix(text: str) -> str:
    text = CALCULATE_PREFIX_RE.sub("", text)
    return NO_CALCULATE_PREFIX_RE.sub("", text).strip()


def _normalize_number(value: str) -> float:
    value = value.strip().replace("\u202f", "").replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")
    return float(value)


def _format_number(value: float, decimals: int = 2) -> str:
    if not math.isfinite(value):
        return str(value)
    if abs(value - round(value)) < 1e-10:
        return str(int(round(value)))
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def _round_value(value: float, decimals: int = 2) -> float | int:
    rounded = round(value, decimals)
    if abs(rounded - round(rounded)) < 1e-10:
        return int(round(rounded))
    return rounded


class _SafeExpressionEvaluator(ast.NodeVisitor):
    _ops = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Pow: lambda a, b: a ** b,
    }
    _unary = {
        ast.UAdd: lambda a: a,
        ast.USub: lambda a: -a,
    }

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise ValueError("Only numeric literals are allowed")

    def visit_BinOp(self, node: ast.BinOp) -> float:
        op_type = type(node.op)
        if op_type not in self._ops:
            raise ValueError("Unsupported operator")
        left = self.visit(node.left)
        right = self.visit(node.right)
        if op_type is ast.Pow and abs(right) > 10:
            raise ValueError("Exponent too large")
        result = self._ops[op_type](left, right)
        if not math.isfinite(result) or abs(result) > 1e15:
            raise ValueError("Result outside safe range")
        return float(result)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        op_type = type(node.op)
        if op_type not in self._unary:
            raise ValueError("Unsupported unary operator")
        return float(self._unary[op_type](self.visit(node.operand)))

    def generic_visit(self, node: ast.AST) -> float:
        raise ValueError(f"Unsafe expression node: {type(node).__name__}")


def _safe_eval_expression(expression: str) -> float:
    cleaned = expression.strip()
    cleaned = cleaned.replace("^", "**")
    cleaned = re.sub(r"(?<=\d),(?=\d)", ".", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned or len(cleaned) > 160:
        raise ValueError("Expression is empty or too long")
    if not re.fullmatch(r"[0-9+\-*/().\s*]+", cleaned):
        raise ValueError("Expression contains unsupported characters")
    tree = ast.parse(cleaned, mode="eval")
    return _SafeExpressionEvaluator().visit(tree)


def _extract_arithmetic_expression(text: str) -> str | None:
    stripped = _strip_control_prefix(text)
    stripped = re.sub(r"\b(rechne|berechne|calculate|was ist|wieviel ist|wie viel ist)\b[:\s]*", "", stripped, flags=re.IGNORECASE)
    stripped = stripped.replace("×", "*").replace("÷", "/")
    stripped = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", stripped)
    match = re.search(r"[-+()0-9][0-9\s,.\-+*/^()]{2,}", stripped)
    if not match:
        return None
    expr = match.group(0).strip()
    if not re.search(r"[+\-*/^]", expr):
        return None
    if re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", expr):
        return None
    return expr


def _calculate_arithmetic(text: str) -> dict[str, Any] | None:
    expression = _extract_arithmetic_expression(text)
    if not expression:
        return None
    try:
        result = _safe_eval_expression(expression)
    except Exception as exc:
        return {
            "domain": "basic_arithmetic",
            "confidence": "low",
            "inputs": {"expression": expression},
            "computed": {},
            "warnings": [f"Arithmetic expression was detected but rejected by the safe parser: {exc}"],
        }
    return {
        "domain": "basic_arithmetic",
        "confidence": "high",
        "inputs": {"expression": expression},
        "computed": {"result": _round_value(result, 6)},
        "formula": expression,
        "warnings": ["Calculated with a restricted local arithmetic parser, not raw eval."],
    }


def _calculate_percentages(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    percent_of = re.search(rf"({NUMBER_RE})\s*%\s*(?:von|of)\s*({NUMBER_RE})", lower)
    if percent_of:
        percent = _normalize_number(percent_of.group(1))
        value = _normalize_number(percent_of.group(2))
        return {
            "domain": "percentages",
            "confidence": "high",
            "inputs": {"percent": percent, "value": value},
            "computed": {"percent_of_value": _round_value(value * percent / 100)},
            "formula": "value * percent / 100",
            "warnings": [],
        }

    vat = re.search(rf"({NUMBER_RE})\s*(?:eur|euro|€)?[\s\S]{{0,30}}\b(?:mit|plus)\s*({NUMBER_RE})\s*%\s*(?:mwst|ust|umsatzsteuer|vat|tax)", lower)
    if vat:
        net = _normalize_number(vat.group(1))
        percent = _normalize_number(vat.group(2))
        gross = net * (1 + percent / 100)
        return {
            "domain": "finance_basic",
            "confidence": "high",
            "inputs": {"net_value": net, "tax_percent": percent},
            "computed": {"tax_amount": _round_value(gross - net), "gross_value": _round_value(gross)},
            "formula": "gross = net * (1 + tax_percent / 100)",
            "warnings": ["Arithmetic support only; no tax/legal interpretation."],
        }

    discount = re.search(rf"({NUMBER_RE})\s*%\s*(?:rabatt|discount)[\s\S]{{0,30}}(?:auf|on)\s*({NUMBER_RE})", lower)
    if discount:
        percent = _normalize_number(discount.group(1))
        value = _normalize_number(discount.group(2))
        amount = value * percent / 100
        return {
            "domain": "finance_basic",
            "confidence": "high",
            "inputs": {"value": value, "discount_percent": percent},
            "computed": {"discount_amount": _round_value(amount), "discounted_value": _round_value(value - amount)},
            "formula": "discounted_value = value * (1 - discount_percent / 100)",
            "warnings": ["Arithmetic support only; no pricing guarantee."],
        }
    return None


def _calculate_unit_conversion(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    units = "|".join(sorted(map(re.escape, UNIT_ALIASES), key=len, reverse=True))
    match = re.search(rf"({NUMBER_RE})\s*({units})\s*(?:in|to|nach|zu)\s*({units})\b", lower)
    if not match:
        return None
    value = _normalize_number(match.group(1))
    source = match.group(2).lower()
    target = match.group(3).lower()
    source_dim, source_factor = UNIT_ALIASES[source]
    target_dim, target_factor = UNIT_ALIASES[target]
    if source_dim != target_dim:
        return {
            "domain": "unit_conversion",
            "confidence": "low",
            "inputs": {"value": value, "source_unit": source, "target_unit": target},
            "computed": {},
            "warnings": [f"Cannot convert {source} to {target}: unit dimensions differ."],
        }
    result = value * source_factor / target_factor
    return {
        "domain": "unit_conversion",
        "confidence": "high",
        "inputs": {"value": value, "source_unit": source, "target_unit": target},
        "computed": {"converted_value": _round_value(result, 6), "target_unit": target},
        "formula": "value * source_factor / target_factor",
        "warnings": [],
    }


def _find_number_before_unit(text: str, unit_pattern: str, window_pattern: str | None = None) -> float | None:
    pattern = rf"({NUMBER_RE})\s*(?:{unit_pattern})"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        start = max(0, match.start() - 40)
        end = min(len(text), match.end() + 40)
        window = text[start:end]
        if window_pattern is None or re.search(window_pattern, window, re.IGNORECASE):
            return _normalize_number(match.group(1))
    return None


def _find_battery_capacity_kwh(text: str) -> tuple[float | None, bool]:
    for unit, is_kw_typo in ((r"kwh\b(?!\s*/)", False), (r"kw\b(?!h)", True)):
        pattern = rf"({NUMBER_RE})\s*(?:{unit})"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            window = text[start:end]
            if re.search(r"akku|batter|capacity|kapazit|netto|brutto", window, re.IGNORECASE):
                return _normalize_number(match.group(1)), is_kw_typo
    return None, False


def _find_range_before_unit(text: str, unit_pattern: str) -> list[float] | None:
    pattern = rf"({NUMBER_RE})\s*(?:-|–|—|bis|to)\s*({NUMBER_RE})\s*{unit_pattern}"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    a = _normalize_number(match.group(1))
    b = _normalize_number(match.group(2))
    return [min(a, b), max(a, b)]


def _calculate_ev_route(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    has_ev_signal = re.search(r"\b(kwh|kw\s+batter|akku|batterie|e-auto|elektroauto|ev|reichweite|verbrauch)\b", lower)
    consumption_range = _find_range_before_unit(text, r"kwh\s*/\s*100\s*km")
    consumption_single = _find_number_before_unit(text, r"kwh\s*/\s*100\s*km")
    battery_kwh, kw_battery_typo = _find_battery_capacity_kwh(text)
    distance_km = _find_number_before_unit(text, r"km\b", r"route|strecke|fahrt|distanz|entfernung|nach|von|für|fuer|km")
    if not has_ev_signal or battery_kwh is None or (consumption_range is None and consumption_single is None):
        return None

    consumption = consumption_range or [float(consumption_single), float(consumption_single)]  # type: ignore[arg-type]
    low_consumption, high_consumption = min(consumption), max(consumption)
    full_range = [battery_kwh / high_consumption * 100, battery_kwh / low_consumption * 100]
    inputs: dict[str, Any] = {
        "battery_kwh": _round_value(battery_kwh),
        "consumption_kwh_per_100km": [_round_value(low_consumption), _round_value(high_consumption)],
    }
    computed: dict[str, Any] = {
        "full_battery_range_km": [_round_value(full_range[0], 0), _round_value(full_range[1], 0)],
    }
    warnings = [
        "Arithmetic support only; no charging curve, weather, speed, elevation, vehicle load, or live charger availability was calculated.",
    ]
    assumptions = ["Battery capacity was treated as usable kWh unless the prompt said otherwise."]
    if kw_battery_typo:
        warnings.append("Prompt likely used kW for battery capacity; interpreted it as kWh capacity for arithmetic.")
    if distance_km:
        route_energy = [distance_km * low_consumption / 100, distance_km * high_consumption / 100]
        inputs["distance_km"] = _round_value(distance_km)
        computed["route_energy_need_kwh"] = [_round_value(route_energy[0], 0), _round_value(route_energy[1], 0)]
        start_soc = _extract_soc_percent(lower, ("start", "anfang", "abfahrt", "los", "voll", "100%"))
        reserve_soc = _extract_soc_percent(lower, ("reserve", "ziel", "ankunft", "rest", "puffer"))
        if start_soc is not None:
            if reserve_soc is None:
                reserve_soc = 0.0
            usable_start = max(0.0, battery_kwh * (start_soc - reserve_soc) / 100)
            missing = [max(0.0, route_energy[0] - usable_start), max(0.0, route_energy[1] - usable_start)]
            inputs["start_soc_percent"] = _round_value(start_soc)
            inputs["reserve_soc_percent"] = _round_value(reserve_soc)
            computed["usable_start_energy_kwh"] = _round_value(usable_start)
            computed["minimum_mid_route_energy_kwh"] = [_round_value(missing[0], 0), _round_value(missing[1], 0)]
    return {
        "domain": "ev_route",
        "confidence": "high",
        "inputs": inputs,
        "computed": computed,
        "assumptions": assumptions,
        "formula": "range_km = battery_kwh / consumption_kwh_per_100km * 100; route_energy_kwh = distance_km * consumption / 100",
        "warnings": warnings,
    }


def _extract_soc_percent(text: str, labels: tuple[str, ...]) -> float | None:
    if "voll" in labels and re.search(r"\bvoll(?:em|er|en)?\b|\bfull\b", text, re.IGNORECASE):
        return 100.0
    label_pattern = "|".join(map(re.escape, labels))
    near_label = re.search(rf"(?:{label_pattern})[\s\S]{{0,35}}?({NUMBER_RE})\s*%", text, re.IGNORECASE)
    if near_label:
        return _normalize_number(near_label.group(1))
    percent_then_label = re.search(rf"({NUMBER_RE})\s*%[\s\S]{{0,35}}?(?:{label_pattern})", text, re.IGNORECASE)
    if percent_then_label:
        return _normalize_number(percent_then_label.group(1))
    return None


def _calculate_fuel_route(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    consumption_range = _find_range_before_unit(text, r"(?:l|liter)\s*/\s*100\s*km")
    consumption_single = _find_number_before_unit(text, r"(?:l|liter)\s*/\s*100\s*km")
    tank_l = _find_number_before_unit(text, r"(?:l|liter)\b", r"tank|tankgröße|tankgroesse")
    distance_km = _find_number_before_unit(text, r"km\b", r"route|strecke|fahrt|distanz|entfernung|nach|von|für|fuer|km")
    if not re.search(r"\b(tank|tanken|kraftstoff|benzin|diesel|verbrauch|l/100\s*km|liter/100\s*km)\b", lower):
        return None
    if tank_l is None or (consumption_range is None and consumption_single is None):
        return None
    consumption = consumption_range or [float(consumption_single), float(consumption_single)]  # type: ignore[arg-type]
    low_consumption, high_consumption = min(consumption), max(consumption)
    full_range = [tank_l / high_consumption * 100, tank_l / low_consumption * 100]
    inputs: dict[str, Any] = {
        "tank_liters": _round_value(tank_l),
        "consumption_l_per_100km": [_round_value(low_consumption), _round_value(high_consumption)],
    }
    computed: dict[str, Any] = {
        "full_tank_range_km": [_round_value(full_range[0]), _round_value(full_range[1])],
    }
    if distance_km:
        fuel_need = [distance_km * low_consumption / 100, distance_km * high_consumption / 100]
        inputs["distance_km"] = _round_value(distance_km)
        computed["route_fuel_need_liters"] = [_round_value(fuel_need[0]), _round_value(fuel_need[1])]
    return {
        "domain": "fuel_route",
        "confidence": "high",
        "inputs": inputs,
        "computed": computed,
        "formula": "range_km = tank_liters / consumption_l_per_100km * 100; route_fuel_liters = distance_km * consumption / 100",
        "warnings": ["Arithmetic support only; no live fuel prices, station availability, traffic, elevation, or route optimization was calculated."],
    }


def _parse_duration_hours(text: str) -> float | None:
    hour_minute = re.search(rf"({NUMBER_RE})\s*(?:h|std|stunden?)\s*(?:und\s*)?({NUMBER_RE})?\s*(?:min|minuten?)?", text, re.IGNORECASE)
    if hour_minute:
        hours = _normalize_number(hour_minute.group(1))
        minutes = _normalize_number(hour_minute.group(2)) if hour_minute.group(2) else 0
        return hours + minutes / 60
    minutes = re.search(rf"({NUMBER_RE})\s*(?:min|minuten?)\b", text, re.IGNORECASE)
    if minutes:
        return _normalize_number(minutes.group(1)) / 60
    return None


def _calculate_time_distance(text: str) -> dict[str, Any] | None:
    distance = _find_number_before_unit(text, r"km\b")
    speed = _find_number_before_unit(text, r"km\s*/\s*h|kmh|km/h")
    duration_h = _parse_duration_hours(text)
    lower = text.lower()
    if distance and speed and re.search(r"\b(wie lange|dauer|zeit|brauche|fahrzeit|time)\b", lower):
        hours = distance / speed
        return {
            "domain": "time_distance",
            "confidence": "high",
            "inputs": {"distance_km": _round_value(distance), "speed_kmh": _round_value(speed)},
            "computed": {"duration_hours": _round_value(hours), "duration_minutes": _round_value(hours * 60)},
            "formula": "time_h = distance_km / speed_kmh",
            "warnings": ["Arithmetic support only; traffic, stops, speed limits, and route shape were not calculated."],
        }
    if distance and duration_h and re.search(r"(geschwindigkeit|tempo|schnitt|durchschnitt|speed)", lower):
        speed_result = distance / duration_h
        return {
            "domain": "time_distance",
            "confidence": "high",
            "inputs": {"distance_km": _round_value(distance), "duration_hours": _round_value(duration_h)},
            "computed": {"average_speed_kmh": _round_value(speed_result)},
            "formula": "speed_kmh = distance_km / time_h",
            "warnings": ["Arithmetic support only; route and traffic were not calculated."],
        }
    return None


def _calculate_all(text: str, forced: bool = False) -> list[dict[str, Any]]:
    config = _config_snapshot()
    calculators = [
        ("ev_route", "ev_route", _calculate_ev_route),
        ("fuel_route", "fuel_route", _calculate_fuel_route),
        ("percentages", "percentages", _calculate_percentages),
        ("unit_conversion", "unit_conversion", _calculate_unit_conversion),
        ("time_distance", "time_distance", _calculate_time_distance),
        ("basic_arithmetic", "basic_arithmetic", _calculate_arithmetic),
    ]
    results: list[dict[str, Any]] = []
    for domain_key, _label, func in calculators:
        if not forced and not config["domains"].get(domain_key, True):
            continue
        result = func(text)
        if result and (result.get("computed") or forced):
            results.append(result)
    return results


def _should_calculate(message: str) -> tuple[bool, str]:
    text = _message_text(message).strip()
    if not text:
        return False, "empty"
    if NO_CALCULATE_PREFIX_RE.match(text):
        return False, "opt-out"
    if CALCULATE_PREFIX_RE.match(text):
        return True, "explicit"
    if _is_status_request(text):
        return False, "status-request"
    if SLASH_COMMAND_RE.match(text):
        return False, "slash-command"
    config = _config_snapshot()
    if not config["enabled"]:
        return False, "disabled"
    mode = str(config["mode"])
    if mode == "conservative" and not CALC_WORD_RE.search(text):
        return False, "conservative-no-trigger"
    if _calculate_all(text):
        return True, "supported-calculation"
    if mode == "aggressive" and CALC_WORD_RE.search(text) and re.search(NUMBER_RE, text):
        return True, "aggressive-numeric"
    return False, "no-supported-calculation"


def _is_status_request(message: str) -> bool:
    return bool(STATUS_REQUEST_RE.search(message))


def _redact_prompt_preview(text: str, limit: int = 180) -> str:
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", text)
    redacted = re.sub(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b", "[redacted-phone]", redacted)
    redacted = re.sub(r"\b[A-Za-z0-9_-]{28,}\b", "[redacted-token]", redacted)
    return redacted[:limit]


def _record_decision(action: str, reason: str, **details: Any) -> dict[str, Any]:
    decision = {
        "ts": time.time(),
        "plugin": "calculation-guard",
        "action": action,
        "reason": reason,
        **details,
    }
    if "prompt" in decision:
        decision["prompt_preview"] = _redact_prompt_preview(str(decision.pop("prompt")))
    DECISIONS.append(decision)
    max_decisions = _config_snapshot()["decision_history"]
    del DECISIONS[:-max_decisions]
    return decision


def _decision_category(decision: dict[str, Any]) -> str:
    if decision.get("action") == "injected":
        return "manual_calculation" if decision.get("reason") == "explicit" else "calculated_and_injected"
    if decision.get("action") == "failed":
        return "failed"
    return "checked_and_skipped"


def _visible_effect(decision: dict[str, Any]) -> str:
    if decision.get("action") == "injected":
        return "calculation_context_injected"
    return "none"


def _diagnose_decision(decision: dict[str, Any]) -> dict[str, Any]:
    category = _decision_category(decision)
    return {
        **decision,
        "category": category,
        "visible_effect": _visible_effect(decision),
        "searched_external_services": False,
        "user_explanation": _user_explanation(decision, category),
    }


def _user_explanation(decision: dict[str, Any], category: str) -> str:
    if category in {"calculated_and_injected", "manual_calculation"}:
        domains = ", ".join(decision.get("domains") or [])
        return f"Calculation Guard hat lokal deterministische Werte berechnet und Kontext injiziert ({domains})."
    if decision.get("reason") == "model-gate-cloud":
        return "Calculation Guard hat wegen Model-Gate keinen automatischen Kontext fuer dieses Cloud-Modell injiziert."
    if decision.get("reason") == "opt-out":
        return "Calculation Guard wurde fuer diesen Turn manuell uebersprungen."
    return f"Calculation Guard hat keinen Kontext injiziert: {decision.get('reason')}."


def _recent_decisions(limit: int = 5) -> list[dict[str, Any]]:
    return [_diagnose_decision(item) for item in DECISIONS[-limit:]]


def _format_context(results: list[dict[str, Any]], reason: str, model: str | None, current_prompt: str) -> str:
    payload = {
        "calculation_guard": {
            "version": __version__,
            "reason": reason,
            "model": model or "unknown",
            "results": results,
        }
    }
    json_payload = json.dumps(payload, ensure_ascii=False, indent=2)
    lines = [
        "[Calculation Guard aktiv]",
        "Für diese aktuelle Nutzerfrage wurden lokal deterministische Rechenwerte berechnet.",
        "Nutze diese Werte für Arithmetik, Einheiten und Plausibilität, statt die Kernrechnung neu zu erraten.",
        "Unterscheide Rechenergebnis, Eingabe und Annahme. Behaupte keine Live-Daten, Optimierung oder regulierte Beratung.",
        "Calculation-Guard-Kontexte aus früheren Turns sind für die aktuelle Antwort ungültig.",
        "[/Calculation Guard aktiv]",
        "",
        "[Calculation Guard: Kontext]",
        f"Aktuelle Nutzerfrage: {_redact_prompt_preview(current_prompt, 500)}",
        "Status: lokal berechnet; keine externen APIs; keine versteckte Gedankenkette.",
        "JSON BEGIN",
        json_payload,
        "JSON END",
        "[/Calculation Guard: Kontext]",
    ]
    context = "\n".join(lines)
    max_chars = _config_snapshot()["max_context_chars"]
    if len(context) > max_chars:
        context = context[: max_chars - 120] + "\n[Calculation Guard: Kontext gekürzt wegen max_context_chars]\n[/Calculation Guard: Kontext]"
    return context


def _format_status_request_context() -> str:
    status = calculation_guard_status({"limit": 10})
    return "\n".join(
        [
            "[Calculation Guard: Diagnose-Status]",
            "Antworte nur mit Calculation-Guard-Status und Diagnose. Benenne JSON-Felder nicht um.",
            "Status-JSON BEGIN",
            status,
            "Status-JSON END",
            "[/Calculation Guard: Diagnose-Status]",
        ]
    )


def calculation_guard_status(args: dict, **kwargs) -> str:
    limit = 5
    if isinstance(args, dict):
        try:
            limit = max(1, min(50, int(args.get("limit", limit))))
        except Exception:
            limit = 5
    decisions = _recent_decisions(limit)
    latest = decisions[-1] if decisions else None
    payload = {
        "plugin": "calculation-guard",
        "version": __version__,
        "status_version": 1,
        "enabled": _config_snapshot()["enabled"],
        "config": _config_snapshot(),
        "external_services_used": False,
        "decisions": decisions,
        "summary": {
            "decision_count": len(DECISIONS),
            "latest_category": latest.get("category") if latest else None,
            "latest_explanation": latest.get("user_explanation") if latest else None,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def calculation_guard_diagnostics(args: dict, **kwargs) -> str:
    return calculation_guard_status(args, **kwargs)


def calculation_guard_config(args: dict, **kwargs) -> str:
    args = args if isinstance(args, dict) else {}
    action = str(args.get("action", "show")).strip().lower()
    config = _read_json_file(CONFIG_PATH)
    if action in {"enable", "disable"}:
        config["enabled"] = action == "enable"
    elif action == "set_mode":
        mode = str(args.get("mode", "")).strip().lower()
        if mode not in {"conservative", "balanced", "aggressive"}:
            return json.dumps({"ok": False, "error": "mode must be conservative, balanced, or aggressive"}, ensure_ascii=False)
        config["mode"] = mode
    elif action == "set_cloud_triggers":
        config["allow_cloud_calculation_triggers"] = bool(args.get("allow", args.get("enabled", False)))
    elif action == "set":
        allowed = {"enabled", "only_local", "allow_cloud_calculation_triggers", "mode", "max_context_chars", "decision_history"}
        for key, value in args.items():
            if key in allowed:
                config[key] = value
        if isinstance(args.get("domains"), dict):
            config["domains"] = {**(config.get("domains") if isinstance(config.get("domains"), dict) else {}), **args["domains"]}
    elif action != "show":
        return json.dumps({"ok": False, "error": f"unknown action: {action}"}, ensure_ascii=False)

    if action != "show":
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json.dumps(
        {
            "ok": True,
            "action": action,
            "config_path": str(CONFIG_PATH),
            "stored_config": config,
            "effective_config": _config_snapshot(),
            "note": "Environment variables override config-file values when set.",
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def pre_llm_calculation_guard(session_id: str, user_message: str, model: str, platform: str, **kwargs):
    current_prompt = _message_text(user_message)
    if _is_status_request(current_prompt):
        decision = _record_decision("injected", "status-request", model=model, provider=platform, prompt=current_prompt, domains=["diagnostics"])
        return {"context": _format_status_request_context(), "metadata": {"calculation_guard": decision}}

    should, reason = _should_calculate(current_prompt)
    if _should_skip_for_model_gate(model, platform, should, reason):
        _record_decision("skipped", "model-gate-cloud", model=model, provider=platform, prompt=current_prompt)
        return None
    if not should:
        _record_decision("skipped", reason, model=model, provider=platform, prompt=current_prompt)
        return None

    forced = reason == "explicit"
    results = _calculate_all(current_prompt, forced=forced)
    if not results:
        _record_decision("skipped", "no-supported-calculation-after-parse", model=model, provider=platform, prompt=current_prompt)
        return None

    domains = [str(item.get("domain")) for item in results]
    decision = _record_decision(
        "injected",
        reason,
        model=model,
        provider=platform,
        prompt=current_prompt,
        domains=domains,
        result_count=len(results),
        results=results,
    )
    return {"context": _format_context(results, reason, model, current_prompt), "metadata": {"calculation_guard": decision}}


TOOLS = [
    {
        "name": "calculation_guard_status",
        "description": "Show recent Calculation Guard diagnostics: decisions, categories, parsed inputs, computed outputs, config snapshot, and visible effect.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        },
    },
    {
        "name": "calculation_guard_diagnostics",
        "description": "Alias for calculation_guard_status.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        },
    },
    {
        "name": "calculation_guard_config",
        "description": "View or update persistent Calculation Guard config stored in ~/.hermes/calculation-guard.json.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["show", "set", "enable", "disable", "set_mode", "set_cloud_triggers"]},
                "mode": {"type": "string", "enum": ["conservative", "balanced", "aggressive"]},
                "allow": {"type": "boolean"},
                "enabled": {"type": "boolean"},
                "only_local": {"type": "boolean"},
                "allow_cloud_calculation_triggers": {"type": "boolean"},
                "max_context_chars": {"type": "integer"},
                "decision_history": {"type": "integer"},
                "domains": {"type": "object"},
            },
        },
    },
]


def register(ctx):
    ctx.register_hook("pre_llm_call", pre_llm_calculation_guard)
    ctx.register_tool(
        name="calculation_guard_status",
        handler=calculation_guard_status,
        description=TOOLS[0]["description"],
        parameters=TOOLS[0]["parameters"],
        toolset="calculation_guard",
    )
    ctx.register_tool(
        name="calculation_guard_diagnostics",
        handler=calculation_guard_diagnostics,
        description=TOOLS[1]["description"],
        parameters=TOOLS[1]["parameters"],
        toolset="calculation_guard",
    )
    ctx.register_tool(
        name="calculation_guard_config",
        handler=calculation_guard_config,
        description=TOOLS[2]["description"],
        parameters=TOOLS[2]["parameters"],
        toolset="calculation_guard",
    )
