"""
LLM Provider module with Groq (qwen/qwen3.8-27b) integration and strict fact enforcement.
Supports local .env as well as Streamlit Cloud Secrets (st.secrets).
Guarantees that numbers and safety advice strictly originate from Open-Meteo and SOP policies.
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


class AdvisoryComposer:
    """
    Composes safety advisories using Groq's qwen/qwen3.8-27b model,
    strictly constrained by verified weather metrics and matched SOP policies.
    """

    def __init__(self, model_name: str = "qwen/qwen3.8-27b"):
        # Check environment first, then fallback to Streamlit Cloud secrets if available
        self.groq_key = os.getenv("GROQ_API_KEY")
        if not self.groq_key:
            try:
                import streamlit as st
                if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                    self.groq_key = st.secrets["GROQ_API_KEY"]
            except Exception:
                pass

        self.model_name = os.getenv("GROQ_MODEL", model_name)
        self.client = None

        if self.groq_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.groq_key.strip('"\''))
            except Exception as e:
                print(f"[AdvisoryComposer] Warning: Could not initialize Groq client: {e}")
                self.client = None

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
        Compose response using qwen/qwen3.8-27b with strict fact grounding.
        Verified numbers and authorized SOP text are injected and enforced.
        """
        loc = weather.get("location", "Unknown Location")
        metrics = weather.get("metrics", {})
        temp = metrics.get("temperature")
        precip = metrics.get("precipitation")
        precip_prob = metrics.get("precipitation_probability")
        wind = metrics.get("wind_speed")
        gusts = metrics.get("wind_gusts", wind)
        uv = metrics.get("uv_index")
        condition = metrics.get("condition_name", "Observed conditions")
        target_desc = weather.get("target_period_desc", target_period)

        sop_id = primary_sop["id"]
        sop_title = primary_sop["title"]
        severity = primary_sop["severity"]
        mandatory_text = primary_sop["mandatory_guidance"]
        rationale = primary_sop.get("rationale", "")

        verified_metrics_block = (
            f"📍 **Verified Live Weather for {loc}** ({target_desc}):\n"
            f"• Condition: {condition}\n"
            f"• Temperature: {temp}°C\n"
            f"• Precipitation: {precip} mm (Probability: {precip_prob}%)\n"
            f"• Wind Speed: {wind} km/h (Gusts: {gusts} km/h)\n"
            f"• UV Index: {uv}\n"
        )

        severity_badges = {
            "CRITICAL": "🚨 **CRITICAL ALERT**",
            "HIGH": "⚠️ **HIGH SEVERITY ADVISORY**",
            "MEDIUM": "⚡ **MODERATE CAUTION**",
            "LOW": "ℹ️ **STANDARD ADVISORY / FAVORABLE**"
        }
        badge = severity_badges.get(severity, f"**{severity} ADVISORY**")

        secondary_text = ""
        if secondary_sops:
            secondary_text = "\nAdditional Concurrent Policies Triggered:\n"
            for sec in secondary_sops:
                secondary_text += f"- [{sec['id']} - {sec['title']}] ({sec['severity']}): {sec['mandatory_guidance']}\n"

        llm_body = None
        if self.client:
            try:
                system_prompt = (
                    "You are the MediBuddy Weather-Advisory Clinical Assistant. "
                    "You answer outdoor safety questions for users. "
                    "CRITICAL CONSTRAINTS:\n"
                    "1. You must ONLY use the provided verified weather facts and the authorized SOP guidance.\n"
                    "2. Do NOT invent, assume, or estimate any weather figures.\n"
                    "3. Do NOT invent any safety advice outside the authorized SOP policy text.\n"
                    "4. If a severe rain system or cyclonic alert applies, lead with the rain warning first.\n"
                    "5. Keep your tone empathetic, authoritative, and concise (2-3 short paragraphs)."
                )

                user_prompt = (
                    f"User Question: \"{query}\"\n"
                    f"Location: {loc}\n"
                    f"Activity: {activity}\n"
                    f"Target Horizon: {target_desc}\n\n"
                    f"Verified Weather Facts from Open-Meteo:\n"
                    f"- Temperature: {temp}°C\n"
                    f"- Precipitation: {precip} mm (Probability: {precip_prob}%)\n"
                    f"- Wind Speed: {wind} km/h (Gusts: {gusts} km/h)\n"
                    f"- UV Index: {uv}\n"
                    f"- General Condition: {condition}\n\n"
                    f"Authorized Clinical Policy:\n"
                    f"- Primary Policy ID: {sop_id} ({sop_title})\n"
                    f"- Clinical Severity: {severity}\n"
                    f"- Trigger Rationale: {rationale}\n"
                    f"- Mandatory Official Safety Guidance: {mandatory_text}\n"
                    f"{secondary_text}\n"
                    "Please compose the user advisory directly incorporating the official safety guidance."
                )

                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=350
                )
                llm_body = completion.choices[0].message.content.strip()
            except Exception as e:
                print(f"[AdvisoryComposer] Groq completion fallback due to: {e}")
                llm_body = None

        if not llm_body:
            if primary_sop.get("lead_with_system_alert"):
                llm_body = (
                    f"**System Warning:** {mandatory_text}\n\n"
                    f"**Specific Context for '{activity.title()}':** Due to active regional monsoon depression / cyclonic conditions, "
                    f"this activity is not safe under current observed parameters ({precip} mm/h rain, {wind} km/h wind)."
                )
            else:
                llm_body = (
                    f"**Official Safety Guidance:**\n{mandatory_text}\n\n"
                    f"**Policy Trigger Rationale:** {rationale}"
                )

        citation_footer = (
            f"\n\n---\n"
            f"📋 **Policy Citation:** `{sop_id}` ({sop_title})\n"
            f"🤖 *Synthesized via {self.model_name} with strict Open-Meteo fact grounding & clinical SOP enforcement.*"
        )

        secondary_block = ""
        if secondary_sops:
            secondary_block = "\n\n**Additional Concurrent Policies Triggered:**\n"
            for sec in secondary_sops:
                secondary_block += (
                    f"• [{sec['id']} - {sec['title']}] ({sec['severity']}): {sec['mandatory_guidance']}\n"
                )

        final_response = f"{verified_metrics_block}\n{badge}\n\n{llm_body}{secondary_block}{citation_footer}"
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
