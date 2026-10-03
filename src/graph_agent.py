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


def extract_entities(
    query: str,
    current_loc: Optional[str],
    current_act: Optional[str],
    current_time: str,
    prev_status: Optional[str],
    weather_service: WeatherService
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extracts location, activity, and time horizon from text with dynamic geocoding awareness,
    retaining prior turn session context when not explicitly overridden.
    """
    q_lower = query.lower().strip()
    q_clean = query.strip().strip("?.!,'\"")

    # 1. Time Horizon Extraction
    time_horizon = current_time if current_time else "current"
    if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["evening", "tonight", "night", "later", "this evening"]):
        time_horizon = "evening"
    elif any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["tomorrow morning", "morning"]):
        time_horizon = "morning"
    elif any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["tomorrow", "next day"]):
        time_horizon = "tomorrow"

    # 2. Activity Extraction using word boundaries
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

    if not activity:
        if any(re.search(r'\b' + re.escape(w) + r'\b', q_lower) for w in ["chess", "carrom", "board game", "reading", "read a book", "indoor"]):
            activity = "indoor_activity"

    # Retain prior activity if available, or default to general outdoor activity
    if not activity:
        activity = current_act if current_act else "outdoor activity"

    # 3. Location Extraction
    location = None
    explicit_candidate = None

    # Step A: Explicit location prepositions ("in <City>", "at <City>", "near <City>", "around <City>", "of <City>", "for <City>")
    loc_matches = list(re.finditer(r'\b(in|at|near|around|of|for)\s+([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+)?)\b', query, re.IGNORECASE))
    for m in reversed(loc_matches):
        prep = m.group(1).lower()
        cand = m.group(2).strip()

        # If preposition is 'for', exclude if followed by an activity, article, or non-location phrase
        if prep == "for":
            if re.match(r'^(?:a|an|the|\d+|run|running|jog|jogging|walk|walking|cycle|cycling|bike|biking|commute|drive|driving|picnic|exercise|workout|lunch|dinner)\b', cand, re.IGNORECASE):
                continue

        cand = re.sub(r'\b(?:today|tonight|now|this\s+evening|evening|morning|tomorrow|the\s+park|work|office|home)\b', '', cand, flags=re.IGNORECASE).strip()
        if cand and not re.match(r'^\d+\s*(?:am|pm)?$', cand, re.IGNORECASE) and len(cand) > 1:
            if cand.lower() in ["run", "running", "jog", "jogging", "walk", "walking", "cycle", "cycling", "bike", "commute", "exercise"]:
                continue

            # Record the first explicit location preposition candidate (e.g. "in AbcDefGhi999Z")
            if not explicit_candidate and prep in ["in", "at", "near", "around", "of"]:
                explicit_candidate = cand

            res, _ = weather_service.geocode_city(cand)
            if res:
                location = res["name"]
                break

    # If an explicit location clause was specified by the user (e.g. "in AbcDefGhi999Z"),
    # but could not be resolved by geocoding, preserve that candidate directly.
    # This prevents hallucinating alternative cities or scanning unrelated dictionary words.
    if not location and explicit_candidate:
        location = explicit_candidate

    # Step B: Direct short response when awaiting location or short query (e.g. "weather of thailand", "of betul", "agra")
    if not location:
        prefixes = [
            "weather of ", "weather in ", "weather for ", "weather at ",
            "forecast of ", "forecast in ", "forecast for ",
            "climate of ", "temperature of ", "temp of ",
            "what about ", "how about ", "is it safe in ", "is it safe at ",
            "how is the weather in ", "how is the weather of ", "how is the weather for ",
            "tell me about ", "check ", "for ", "in ", "of ", "at ", "near ", "around ", "to "
        ]
        candidate = q_clean
        for p in prefixes:
            if candidate.lower().startswith(p):
                candidate = candidate[len(p):].strip()
                break
        candidate = re.sub(r'\b(?:today|tonight|now|this\s+evening|evening|morning|tomorrow)\b', '', candidate, flags=re.IGNORECASE).strip()
        if candidate and candidate.lower() not in ["yes", "no", "ok", "okay", "sure", "why", "what", "run", "cycle", "walk"]:
            res, _ = weather_service.geocode_city(candidate)
            if res:
                location = res["name"]

    # Step C: Check individual non-stopwords against geocoding (only for proper single-word queries)
    if not location:
        words = [w.strip("?,.! ") for w in re.split(r'[\s,]+', q_clean) if len(w) > 2]
        stopwords = {
            "weather", "forecast", "climate", "temperature", "safe", "outside", "outdoor", "activity",
            "today", "tonight", "morning", "evening", "what", "about", "how", "tell", "check", "please",
            "can", "should", "would", "could", "will", "shall", "might", "may", "must",
            "like", "cycle", "cycling", "bike", "biking", "run", "running",
            "jog", "jogging", "walk", "walking", "stroll", "ride", "riding", "scooty", "scooter",
            "for", "the", "and", "but", "with", "from", "into", "onto", "out", "over", "under",
            "all", "any", "some", "our", "you", "your", "they", "them", "this", "that", "there",
            "here", "where", "when", "which", "who", "whom", "whose", "why", "how", "good",
            "bad", "hot", "cold", "warm", "cool", "want", "need", "take", "taking", "make",
            "making", "have", "having", "been", "being", "does", "done", "doing", "just",
            "very", "much", "more", "most", "also", "even", "ever", "never", "only", "then",
            "than", "now", "yes", "no", "okay", "sure", "travel", "drive", "driving", "commute",
            "picnic", "park", "sports", "cricket", "match", "game", "elderly", "children", "baby",
            "kid", "kids", "senior", "grandparents"
        }
        candidates_from_words = [w for w in words if w.lower() not in stopwords]
        for w in candidates_from_words:
            res, _ = weather_service.geocode_city(w)
            if res:
                location = res["name"]
                break

    # Step D: Fall back to session memory location if available
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
        prev_time = state.get("time_horizon", "current")
        prev_status = state.get("status")

        loc, act, time_hz = extract_entities(
            query=query,
            current_loc=prev_loc,
            current_act=prev_act,
            current_time=prev_time,
            prev_status=prev_status,
            weather_service=self.weather_service
        )
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
                "weather_error": geo_err or f"Could not resolve location '{location}'.",
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
