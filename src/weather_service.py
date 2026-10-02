"""
Weather service client interfacing with the free Open-Meteo API.
Provides geocoding and live meteorological observation/forecast retrieval.
"""

import requests
from typing import Dict, Any, Optional, Tuple

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherService:
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def geocode_city(self, city_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Resolve a city or place name into geographic coordinates using Open-Meteo Geocoding.
        Returns (location_data, error_message).
        """
        if not city_name or not city_name.strip():
            return None, "No location provided."

        clean_name = city_name.strip().strip("?,.!")
        params = {"name": clean_name, "count": 1, "language": "en", "format": "json"}

        try:
            resp = requests.get(self.GEOCODING_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                return None, f"Geocoding service returned HTTP status {resp.status_code}."

            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None, f"Could not resolve location '{clean_name}'. Please verify spelling or specify a known city."

            top_match = results[0]
            resolved = {
                "name": top_match.get("name", clean_name),
                "latitude": float(top_match.get("latitude")),
                "longitude": float(top_match.get("longitude")),
                "country": top_match.get("country", ""),
                "admin1": top_match.get("admin1", "")
            }
            return resolved, None
        except requests.exceptions.RequestException as e:
            return None, f"Network error while connecting to geocoding service: {str(e)}"

    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        resolved_name: str,
        time_target: str = "current"
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch verified live weather and hourly forecast from Open-Meteo.
        Explicitly requests required metrics as per Open-Meteo API specifications.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "rain",
                "showers",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
                "uv_index"
            ],
            "hourly": [
                "temperature_2m",
                "precipitation_probability",
                "precipitation",
                "wind_speed_10m",
                "uv_index"
            ],
            "timezone": "auto"
        }

        try:
            resp = requests.get(self.FORECAST_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                return None, f"Weather forecast service returned HTTP {resp.status_code}."

            data = resp.json()
            current = data.get("current", {})
            if not current:
                return None, "Weather service returned metadata without current observation values."

            code = int(current.get("weather_code", 0))
            condition_desc = WMO_WEATHER_CODES.get(code, f"Condition code {code}")

            hourly = data.get("hourly", {})
            precip_prob_list = hourly.get("precipitation_probability", [])
            precip_prob = float(precip_prob_list[0]) if precip_prob_list else 0.0

            extracted_temp = float(current.get("temperature_2m", 0.0))
            extracted_wind = float(current.get("wind_speed_10m", 0.0))
            extracted_gusts = float(current.get("wind_gusts_10m", extracted_wind))
            extracted_precip = float(current.get("precipitation", 0.0))
            extracted_uv = float(current.get("uv_index", 0.0))
            extracted_humidity = float(current.get("relative_humidity_2m", 50.0))

            is_evening_query = any(w in time_target.lower() for w in ["evening", "tonight", "night", "later"])
            target_period_desc = "current observations"

            if is_evening_query and hourly.get("time"):
                times = hourly.get("time", [])
                evening_indices = [
                    i for i, t in enumerate(times[:24])
                    if any(h in t for h in ["T18:", "T19:", "T20:", "T21:"])
                ]
                if evening_indices:
                    idx = evening_indices[0]
                    target_period_desc = f"evening forecast ({times[idx].split('T')[-1]})"
                    if hourly.get("temperature_2m"):
                        extracted_temp = float(hourly["temperature_2m"][idx])
                    if hourly.get("wind_speed_10m"):
                        extracted_wind = float(hourly["wind_speed_10m"][idx])
                    if hourly.get("precipitation_probability"):
                        precip_prob = float(hourly["precipitation_probability"][idx])
                    if hourly.get("precipitation"):
                        extracted_precip = float(hourly["precipitation"][idx])
                    if hourly.get("uv_index"):
                        extracted_uv = float(hourly["uv_index"][idx])

            weather_record = {
                "location": resolved_name,
                "latitude": latitude,
                "longitude": longitude,
                "query_time_target": time_target,
                "target_period_desc": target_period_desc,
                "observation_time": current.get("time"),
                "metrics": {
                    "temperature": round(extracted_temp, 1),
                    "relative_humidity": round(extracted_humidity, 1),
                    "precipitation": round(extracted_precip, 2),
                    "precipitation_probability": round(precip_prob, 1),
                    "wind_speed": round(extracted_wind, 1),
                    "wind_gusts": round(extracted_gusts, 1),
                    "uv_index": round(extracted_uv, 1),
                    "weather_code": code,
                    "condition_name": condition_desc
                }
            }
            return weather_record, None

        except requests.exceptions.RequestException as e:
            return None, f"Failed to communicate with Open-Meteo weather endpoint: {str(e)}"
