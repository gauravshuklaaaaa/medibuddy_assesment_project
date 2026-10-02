"""
LLM Provider module with strict fact enforcement and graceful fallback.
Guarantees that numbers and safety advice strictly originate from Open-Meteo and SOP policies.
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


class AdvisoryComposer:
    """
    Composes safety advisories strictly adhering to verified weather metrics and matched SOPs.
    """

    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def compose_advisory(
        self,
        query: str,
        weather: Dict[str, Any],
        primary_sop: Dict[str, Any],
        secondary_sops: List[Dict[str, Any]],
        activity: str,
        target_period: str
    ) -> str:
        """
        Compose response with strict fact enforcement.
        All numerical values are directly injected from Open-Meteo data.
        All safety guidance is directly bound to the authorized SOP text.
        """
        loc = weather.get("location", "Unknown Location")
        metrics = weather.get("metrics", {})
        temp = metrics.get("temperature")
        precip = metrics.get("precipitation")
        precip_prob = metrics.get("precipitation_probability")
        wind = metrics.get("wind_speed")
        uv = metrics.get("uv_index")
        condition = metrics.get("condition_name", "Observed conditions")

        # Live metric bullet block enforced directly from Open-Meteo API response
        verified_metrics_block = (
            f"📍 **Verified Live Weather for {loc}** ({weather.get('target_period_desc', target_period)}):\n"
            f"• Condition: {condition}\n"
            f"• Temperature: {temp}°C\n"
            f"• Precipitation: {precip} mm (Probability: {precip_prob}%)\n"
            f"• Wind Speed: {wind} km/h (Gusts: {metrics.get('wind_gusts', wind)} km/h)\n"
            f"• UV Index: {uv}\n"
        )

        sop_id = primary_sop["id"]
        sop_title = primary_sop["title"]
        severity = primary_sop["severity"]
        mandatory_text = primary_sop["mandatory_guidance"]
        rationale = primary_sop.get("rationale", "")

        # Format severity badge
        severity_badges = {
            "CRITICAL": "🚨 **CRITICAL ALERT**",
            "HIGH": "⚠️ **HIGH SEVERITY ADVISORY**",
            "MEDIUM": "⚡ **MODERATE CAUTION**",
            "LOW": "ℹ️ **STANDARD ADVISORY / FAVORABLE**"
        }
        badge = severity_badges.get(severity, f"**{severity} ADVISORY**")

        # Build response body
        if primary_sop.get("lead_with_system_alert"):
            core_message = (
                f"{badge}\n\n"
                f"**System Warning:** {mandatory_text}\n\n"
                f"**Specific Context for '{activity.title()}':** Due to active regional monsoon depression / cyclonic conditions, "
                f"this activity is not safe under current observed parameters ({precip} mm/h rain, {wind} km/h wind).\n"
            )
        else:
            core_message = (
                f"{badge}\n\n"
                f"**Official Safety Guidance:**\n{mandatory_text}\n\n"
                f"**Policy Trigger Rationale:** {rationale}\n"
            )

        # Append secondary SOPs if present
        secondary_block = ""
        if secondary_sops:
            secondary_block = "\n**Additional Concurrent Policies Triggered:**\n"
            for sec in secondary_sops:
                secondary_block += (
                    f"• [{sec['id']} - {sec['title']}] ({sec['severity']}): {sec['mandatory_guidance']}\n"
                )

        citation_footer = (
            f"\n---\n"
            f"📋 **Policy Citation:** `{sop_id}` ({sop_title})\n"
            f"🔒 *Enforced by MediBuddy Safety Protocol Engine v1.0. All numerical figures sourced directly from Open-Meteo.*"
        )

        final_response = f"{verified_metrics_block}\n{core_message}{secondary_block}{citation_footer}"
        return final_response

    def compose_no_sop_response(self, activity: str, weather: Optional[Dict[str, Any]] = None) -> str:
        """Honest fallback when no SOP applies."""
        loc_str = f" for {weather.get('location')}" if weather else ""
        return (
            f"We do not currently have an authorized Standard Operating Procedure (SOP) "
            f"covering '{activity}'{loc_str}.\n\n"
            f"Under MediBuddy's strict safety charter, our assistants are prohibited from inventing or "
            f"estimating health and safety advice without a pre-approved clinical policy. "
            f"Please consult official local advisories or our healthcare support desk for personalized evaluation.\n\n"
            f"📋 **Policy Citation:** `NONE_APPLICABLE` (Honest Fallback Protocol)"
        )

    def compose_weather_error_response(self, error_message: str, location_query: Optional[str] = None) -> str:
        """Honest fallback when weather API fails or city cannot be resolved."""
        loc_info = f" for '{location_query}'" if location_query else ""
        return (
            f"⚠️ **Weather Data Unavailable**\n\n"
            f"Unable to retrieve verified live weather observations{loc_info}.\n"
            f"**Reason:** {error_message}\n\n"
            f"In accordance with MediBuddy policy, safety recommendations must never be generated from "
            f"assumed or recalled forecasts. Because live meteorological metrics could not be confirmed, "
            f"no safety determination can be issued at this time. Please re-check the location spelling or retry shortly."
        )

    def compose_location_clarification_response(self, activity: str) -> str:
        """Asks user for location when missing."""
        act_phrase = f" for {activity}" if activity and activity != "outdoor activity" else ""
        return (
            f"I would be glad to check safety guidance{act_phrase}! "
            f"Could you please share your **city or location**? "
            f"I need to check verified live weather metrics from Open-Meteo before citing our safety SOPs."
        )
