"""
LangGraph implementation for the MediBuddy Weather-Advisory Support Bot.
Implements a true directed state graph with multiple conditional branches,
multi-turn session memory with MemorySaver, and strict SOP fact grounding.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.weather_service import WeatherService
from src.sop_engine import SOPEngine
from src.llm_provider import AdvisoryComposer


class WeatherBotState(TypedDict, total=False):
    session_id: str
    user_query: str
    location: Optional[str]
    activity: Optional[str]
    time_horizon: str
    weather_data: Optional[Dict[str, Any]]
    weather_error: Optional[str]
    matched_sops: List[Dict[str, Any]]
    selected_sop: Optional[Dict[str, Any]]
    secondary_sops: List[Dict[str, Any]]
    resolution_rationale: Optional[str]
    final_response: str
    status: str


def extract_entities(query: str, current_loc: Optional[str], current_act: Optional[str]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extracts location, activity, and time horizon from text with word-boundary awareness,
    retaining prior turn session context when not explicitly overridden.
    """
    q_lower = query.lower()

    # 1. Time Horizon Extraction
    time_horizon = "current"
    if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["evening", "tonight", "night", "later", "this evening"]):
        time_horizon = "evening"
    elif any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["tomorrow morning", "morning"]):
        time_horizon = "morning"
    elif any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["tomorrow", "next day"]):
        time_horizon = "tomorrow"

    # 2. Activity Extraction using word boundaries to prevent substring pollution (e.g. 'pet' in 'competition')
    activity = None
    activity_keywords = {
        "cycling": ["cycle", "cycling", "bike", "biking", "bicycle", "two-wheeler", "two wheeler", "scooty", "scooter", "motorcycle", "riding"],
        "running": ["run", "running", "jog", "jogging", "marathon", "sprint"],
        "walking": ["walk", "walking", "stroll", "dog walk", "walk my dog"],
        "travel": ["travel", "commute", "driving", "drive", "road trip", "highway", "transit", "flyover", "cab", "bus"],
        "picnic": ["picnic", "park", "outing", "gathering", "bbq", "day out", "lawn"],
        "pet": ["pet", "dog", "puppy", "pavement walk"],
        "sports": ["cricket", "football", "tennis", "soccer", "outdoor match", "training"],
        "vulnerable": ["kid", "baby", "children", "child", "elderly", "grandparents", "senior"]
    }

    for act_key, keywords in activity_keywords.items():
        if any(re.search(r'\b' + re.escape(kw) + r'\b', q_lower) for kw in keywords):
            activity = act_key
            break

    # If activity not mentioned, check if query contains indoor activities
    if not activity:
        if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["chess", "carrom", "board game", "reading", "read a book", "indoor"]):
            activity = "indoor_activity"

    # Fall back to session memory if available and not overridden
    if not activity and current_act:
        activity = current_act

    # 3. Location Extraction
    location = None
    known_cities = [
        "bhopal", "mumbai", "delhi", "bengaluru", "bangalore", "chennai", "kolkata",
        "hyderabad", "pune", "ahmedabad", "jaipur", "lucknow", "chandigarh", "patna",
        "surat", "nagpur", "indore", "thane", "visakhapatnam", "vadodara", "ghaziabad",
        "london", "new york", "berlin", "tokyo", "singapore", "paris", "sydney"
    ]

    for c in known_cities:
        if re.search(r'\b' + re.escape(c) + r'\b', q_lower):
            location = c.title()
            break

    if not location:
        # Check prepositions: in / at / near / around <City> (supports alphanumeric candidate)
        match = re.search(r'\b(?:in|at|near|around)\s+([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+)?)\b', query, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in ["the morning", "the evening", "the park", "my area", "work", "office", "a park", "the car"]:
                location = candidate

    # Fall back to session memory location if available
    if not location and current_loc:
        location = current_loc

    return location, activity, time_horizon


class WeatherAdvisoryGraph:
    def __init__(self, sops_path: str = "data/sops.json"):
        self.weather_service = WeatherService()
        self.sop_engine = SOPEngine(sops_path)
        self.composer = AdvisoryComposer()
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(WeatherBotState)

        workflow.add_node("extract_intent", self.extract_intent_node)
        workflow.add_node("clarify_location", self.clarify_location_node)
        workflow.add_node("fetch_weather", self.fetch_weather_node)
        workflow.add_node("fallback_weather_error", self.fallback_weather_error_node)
        workflow.add_node("evaluate_sops", self.evaluate_sops_node)
        workflow.add_node("no_sop", self.no_sop_node)
        workflow.add_node("conflict_resolution", self.conflict_resolution_node)
        workflow.add_node("generate_advisory", self.generate_advisory_node)

        workflow.set_entry_point("extract_intent")

        workflow.add_conditional_edges(
            "extract_intent",
            self._route_after_intent,
            {
                "clarify_location": "clarify_location",
                "fetch_weather": "fetch_weather"
            }
        )
        workflow.add_edge("clarify_location", END)

        workflow.add_conditional_edges(
            "fetch_weather",
            self._route_after_weather,
            {
                "weather_failed": "fallback_weather_error",
                "weather_success": "evaluate_sops"
            }
        )
        workflow.add_edge("fallback_weather_error", END)

        workflow.add_conditional_edges(
            "evaluate_sops",
            self._route_after_sops,
            {
                "no_match": "no_sop",
                "matches_found": "conflict_resolution"
            }
        )
        workflow.add_edge("no_sop", END)

        workflow.add_edge("conflict_resolution", "generate_advisory")
        workflow.add_edge("generate_advisory", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def extract_intent_node(self, state: WeatherBotState) -> Dict[str, Any]:
        query = state.get("user_query", "")
        prev_loc = state.get("location")
        prev_act = state.get("activity")

        loc, act, time_hz = extract_entities(query, prev_loc, prev_act)
        return {
            "location": loc,
            "activity": act or "outdoor activity",
            "time_horizon": time_hz,
            "status": "intent_extracted"
        }

    def clarify_location_node(self, state: WeatherBotState) -> Dict[str, Any]:
        activity = state.get("activity", "outdoor activity")
        response = self.composer.compose_location_clarification_response(activity)
        return {
            "final_response": response,
            "status": "awaiting_location"
        }

    def fetch_weather_node(self, state: WeatherBotState) -> Dict[str, Any]:
        location = state.get("location", "")
        time_target = state.get("time_horizon", "current")

        loc_data, geo_err = self.weather_service.geocode_city(location)
        if geo_err or not loc_data:
            return {
                "weather_data": None,
                "weather_error": geo_err or "Unknown geocoding failure.",
                "status": "weather_failed"
            }

        w_data, w_err = self.weather_service.fetch_weather(
            latitude=loc_data["latitude"],
            longitude=loc_data["longitude"],
            resolved_name=loc_data["name"],
            time_target=time_target
        )

        if w_err or not w_data:
            return {
                "weather_data": None,
                "weather_error": w_err or "Weather forecast service unreachable.",
                "status": "weather_failed"
            }

        return {
            "weather_data": w_data,
            "weather_error": None,
            "status": "weather_fetched"
        }

    def fallback_weather_error_node(self, state: WeatherBotState) -> Dict[str, Any]:
        err_msg = state.get("weather_error", "Service unavailable.")
        loc_str = state.get("location")
        response = self.composer.compose_weather_error_response(err_msg, loc_str)
        return {
            "final_response": response,
            "status": "failed_honestly"
        }

    def evaluate_sops_node(self, state: WeatherBotState) -> Dict[str, Any]:
        activity = state.get("activity", "outdoor activity")
        weather = state.get("weather_data", {})
        time_target = state.get("time_horizon", "current")

        matched = self.sop_engine.match_sops(activity, weather, time_target)
        return {
            "matched_sops": matched,
            "status": "sops_evaluated"
        }

    def no_sop_node(self, state: WeatherBotState) -> Dict[str, Any]:
        activity = state.get("activity", "this activity")
        weather = state.get("weather_data")
        response = self.composer.compose_no_sop_response(activity, weather)
        return {
            "final_response": response,
            "status": "no_guidance_available"
        }

    def conflict_resolution_node(self, state: WeatherBotState) -> Dict[str, Any]:
        matched = state.get("matched_sops", [])
        resolution = self.sop_engine.resolve_conflicts(matched)

        return {
            "selected_sop": resolution["primary_sop"],
            "secondary_sops": resolution["secondary_sops"],
            "resolution_rationale": resolution["resolution_strategy"],
            "status": "conflict_resolved"
        }

    def generate_advisory_node(self, state: WeatherBotState) -> Dict[str, Any]:
        query = state.get("user_query", "")
        weather = state.get("weather_data", {})
        primary_sop = state.get("selected_sop")
        secondary_sops = state.get("secondary_sops", [])
        activity = state.get("activity", "outdoor activity")
        target_period = state.get("time_horizon", "current")

        response = self.composer.compose_advisory(
            query=query,
            weather=weather,
            primary_sop=primary_sop,
            secondary_sops=secondary_sops,
            activity=activity,
            target_period=target_period
        )

        return {
            "final_response": response,
            "status": "advisory_generated"
        }

    def _route_after_intent(self, state: WeatherBotState) -> str:
        loc = state.get("location")
        if not loc or not loc.strip():
            return "clarify_location"
        return "fetch_weather"

    def _route_after_weather(self, state: WeatherBotState) -> str:
        if state.get("weather_error") or not state.get("weather_data"):
            return "weather_failed"
        return "weather_success"

    def _route_after_sops(self, state: WeatherBotState) -> str:
        matched = state.get("matched_sops", [])
        if not matched:
            return "no_match"
        return "matches_found"

    def process_message(self, user_query: str, session_id: str = "default_session") -> Dict[str, Any]:
        config = {"configurable": {"thread_id": session_id}}
        initial_input = {"user_query": user_query, "session_id": session_id}
        result = self.graph.invoke(initial_input, config=config)
        return result
