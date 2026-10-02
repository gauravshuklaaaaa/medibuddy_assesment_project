"""
SOP Rule Engine for MediBuddy Weather Advisory Support Bot.
Dynamically loads and evaluates Standard Operating Procedures from data/sops.json.
Enforces deterministic rule evaluation, conflict resolution, and full traceability.
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple

SEVERITY_WEIGHTS = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1
}


class SOPEngine:
    def __init__(self, sops_file_path: str = "data/sops.json"):
        self.sops_file_path = sops_file_path
        self._sops_cache = None

    def load_sops(self, force_reload: bool = True) -> List[Dict[str, Any]]:
        """
        Dynamically load SOPs from JSON file.
        force_reload=True ensures live updates during reviews take effect immediately.
        """
        if self._sops_cache is not None and not force_reload:
            return self._sops_cache

        if not os.path.exists(self.sops_file_path):
            return []

        with open(self.sops_file_path, "r", encoding="utf-8") as f:
            self._sops_cache = json.load(f)
        return self._sops_cache

    def activity_matches(self, user_activity: str, rule_activities: List[str]) -> bool:
        """Check if user activity matches rule target activities."""
        if not user_activity:
            return False
        clean_act = user_activity.lower().strip()
        if "all" in rule_activities:
            return True
        for act in rule_activities:
            if act in clean_act or clean_act in act:
                return True
        return False

    def evaluate_sop(
        self,
        sop: Dict[str, Any],
        activity: str,
        weather: Dict[str, Any],
        time_target: str = "current"
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates a single SOP against the extracted activity and verified weather metrics.
        Returns (is_matched, rationale_detail).
        """
        metrics = weather.get("metrics", {})
        temp = metrics.get("temperature", 0.0)
        precip = metrics.get("precipitation", 0.0)
        precip_prob = metrics.get("precipitation_probability", 0.0)
        wind = metrics.get("wind_speed", 0.0)
        gusts = metrics.get("wind_gusts", wind)
        uv = metrics.get("uv_index", 0.0)
        humidity = metrics.get("relative_humidity", 50.0)
        code = metrics.get("weather_code", 0)

        # 1. System override rule (e.g. cyclonic monsoon / low-pressure depression)
        if sop.get("rule_type") == "system_override":
            triggers = sop.get("trigger_conditions", {})
            min_precip = triggers.get("min_precipitation", 30.0)
            if precip >= min_precip:
                return True, f"Regional severe precipitation of {precip} mm/h exceeded threshold ({min_precip} mm/h)."
            for cond in triggers.get("or_conditions", []):
                if "min_precipitation" in cond and "min_wind_speed" in cond:
                    if precip >= cond["min_precipitation"] and wind >= cond["min_wind_speed"]:
                        return True, f"Combined rain ({precip} mm/h) and squally wind ({wind} km/h) active."
                if "weather_codes" in cond and code in cond["weather_codes"]:
                    return True, f"Severe thunderstorm / convective weather code {code} active."
            return False, None

        # Check activity relevance
        if not self.activity_matches(activity, sop.get("applies_to_activities", [])):
            return False, None

        # 2. Fuzzy Composite rule (e.g. Picnic / Park gathering suitability)
        if sop.get("rule_type") == "fuzzy_composite":
            triggers = sop.get("trigger_conditions", {})
            ideal = triggers.get("ideal_envelope", {})
            tolerable = triggers.get("tolerable_envelope", {})

            is_ideal = (
                ideal.get("min_temp", 18.0) <= temp <= ideal.get("max_temp", 28.0) and
                precip <= ideal.get("max_precipitation", 0.1) and
                wind <= ideal.get("max_wind_speed", 20.0) and
                uv <= ideal.get("max_uv_index", 6.5)
            )
            is_tolerable = (
                tolerable.get("min_temp", 15.0) <= temp <= tolerable.get("max_temp", 33.0) and
                precip <= tolerable.get("max_precipitation", 1.0) and
                wind <= tolerable.get("max_wind_speed", 30.0)
            )

            if is_ideal:
                return True, f"Conditions align with the Ideal Comfort Envelope (Temp: {temp}°C, Wind: {wind} km/h, Rain: {precip} mm, UV: {uv})."
            elif is_tolerable:
                return True, f"Conditions fall within Tolerable/Marginal Envelope (Temp: {temp}°C, Wind: {wind} km/h, Rain: {precip} mm, UV: {uv}). Recommend precautionary shade/tarps."
            else:
                return True, f"Conditions exceed tolerable outdoor comfort limits (Temp: {temp}°C, Wind: {wind} km/h, Rain: {precip} mm). Not ideal for gatherings."

        # 3. Baseline Favorable rules (LOW severity standard guidance)
        if sop.get("rule_type") == "baseline_favorable":
            triggers = sop.get("trigger_conditions", {})
            min_t = triggers.get("min_temp", -999.0)
            max_t = triggers.get("max_temp", 999.0)
            max_w = triggers.get("max_wind_speed", 999.0)
            max_p = triggers.get("max_precipitation", 999.0)
            max_uv = triggers.get("max_uv_index", 999.0)
            ex_codes = triggers.get("excluded_weather_codes", [])

            if (min_t <= temp <= max_t and
                wind <= max_w and
                precip <= max_p and
                uv <= max_uv and
                code not in ex_codes):
                return True, f"Conditions fall comfortably within safe baseline operating parameters (Temp: {temp}°C, Wind: {wind} km/h, Rain: {precip} mm, UV: {uv})."
            return False, None

        # 4. Deterministic Hazard Threshold SOPs
        triggers = sop.get("trigger_conditions", {})

        # UV rule with optional time window
        if "min_uv_index" in triggers:
            min_uv = triggers["min_uv_index"]
            is_evening = any(w in time_target.lower() for w in ["evening", "night", "dusk", "post-sunset"])
            if uv >= min_uv and not is_evening:
                return True, f"Recorded UV index of {uv} meets or exceeds critical threshold of {min_uv}."

        # Wind speed & gusts
        if "min_wind_speed" in triggers:
            min_w = triggers["min_wind_speed"]
            min_g = triggers.get("min_wind_gusts", min_w)
            if wind >= min_w or gusts >= min_g:
                return True, f"Recorded wind speed of {wind} km/h (gusts {gusts} km/h) exceeds safe threshold of {min_w} km/h."

        # Precipitation & rain probability
        if "min_precipitation" in triggers or "or_precipitation_prob" in triggers:
            min_p = triggers.get("min_precipitation", 999.0)
            min_prob = triggers.get("or_precipitation_prob", 999.0)
            if precip >= min_p or precip_prob >= min_prob:
                return True, f"Rainfall rate ({precip} mm/h) or precipitation probability ({precip_prob}%) breached threshold ({min_p} mm/h or {min_prob}%)."

        # High or low temperature limits
        if "min_temperature" in triggers and "max_temperature" in triggers:
            min_t = triggers["min_temperature"]
            max_t = triggers["max_temperature"]
            if min_t <= temp <= max_t:
                return True, f"Ambient temperature of {temp}°C falls within thermal caution range ({min_t}°C - {max_t}°C)."

        # Extreme temperature for vulnerable groups
        if "extreme_heat_threshold" in triggers or "extreme_cold_threshold" in triggers:
            heat_limit = triggers.get("extreme_heat_threshold", 40.0)
            cold_limit = triggers.get("extreme_cold_threshold", 5.0)
            if temp >= heat_limit or temp <= cold_limit:
                return True, f"Ambient temperature of {temp}°C breaches vulnerable physiology thresholds (Heat: {heat_limit}°C, Cold: {cold_limit}°C)."

        # Fog & visibility
        if "weather_codes" in triggers:
            codes = triggers["weather_codes"]
            if code in codes or (humidity >= triggers.get("min_relative_humidity", 95.0) and wind <= triggers.get("max_wind_speed", 10.0)):
                return True, f"Atmospheric obstruction detected (Weather code: {code}, Humidity: {humidity}%)."

        # High humidity
        if "min_relative_humidity" in triggers and "min_temperature" in triggers:
            min_h = triggers["min_relative_humidity"]
            min_t = triggers["min_temperature"]
            if humidity >= min_h and temp >= min_t:
                return True, f"High relative humidity ({humidity}%) combined with heat ({temp}°C) creates oppressive conditions."

        return False, None

    def match_sops(
        self,
        activity: str,
        weather: Dict[str, Any],
        time_target: str = "current"
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all active SOPs and return a list of matched rules with rationales.
        """
        sops = self.load_sops(force_reload=True)
        matched = []

        for sop in sops:
            is_match, reason = self.evaluate_sop(sop, activity, weather, time_target)
            if is_match:
                matched.append({
                    "id": sop["id"],
                    "title": sop["title"],
                    "category": sop["category"],
                    "severity": sop["severity"],
                    "mandatory_guidance": sop["mandatory_guidance"],
                    "lead_with_system_alert": sop.get("lead_with_system_alert", False),
                    "rationale": reason,
                    "required_metrics": sop.get("required_metrics", [])
                })

        return matched

    def resolve_conflicts(self, matched_sops: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Defended Conflict Resolution Policy:
        1. If a CRITICAL system-wide meteorological alert matches, it is the primary policy.
        2. Otherwise, rank matched rules by severity (CRITICAL > HIGH > MEDIUM > LOW).
        3. The highest-ranked rule is selected as Primary SOP.
        4. Any secondary matching rules are attached as supplementary cautions.
        """
        if not matched_sops:
            return {
                "has_match": False,
                "primary_sop": None,
                "secondary_sops": [],
                "resolution_strategy": "No SOP matched the query or conditions."
            }

        sorted_sops = sorted(
            matched_sops,
            key=lambda x: (
                1 if x.get("lead_with_system_alert") else 0,
                SEVERITY_WEIGHTS.get(x["severity"], 0)
            ),
            reverse=True
        )

        primary = sorted_sops[0]
        secondary = sorted_sops[1:]

        strategy_desc = (
            f"Selected [{primary['id']}] as primary guidance based on severity rank "
            f"({primary['severity']}). {len(secondary)} additional rule(s) retained as secondary advisories."
        )

        return {
            "has_match": True,
            "primary_sop": primary,
            "secondary_sops": secondary,
            "resolution_strategy": strategy_desc
        }
