from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("weather",log_level="ERROR")

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0 (contact@weatherapp.com)"



async def make_nws_request(url:str) -> dict[str , Any]|None:
    """make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error {e.response.status_code} {e.response.reason_phrase}"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}




def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature.get("properties", {})
    return f"""
                Event: {props.get("event", "Unknown")}
                Area: {props.get("areaDesc", "Unknown")}
                Severity: {props.get("severity", "Unknown")}
                Description: {props.get("description", "No description available")}
                Instructions: {props.get("instruction", "No specific instructions available")}
            """




@mcp.tool()
async def get_alerts(state: str) -> str:
    """
    Get weather alerts for a US state.
    
    Args:
        state (str): The two-letter state abbreviation (e.g., 'CA' for California).

    """

    url = f"{NWS_API_BASE}/alerts/active?area={state}"
    data = await make_nws_request(url)
    
    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    alerts = data["features"]
    if not alerts:
        return "No active alerts found for this state."

    formatted_alerts = [format_alert(alert) for alert in alerts]
    return "\n---\n".join(formatted_alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """
    Get the weather forecast for a specific latitude and longitude.
    
    Args:
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.
    """

    # First get gridpoint from coordinates
    # Format coordinates to 4 decimal places for API compatibility
    formatted_lat = f"{latitude:.4f}"
    formatted_lon = f"{longitude:.4f}"
    points_url = f"{NWS_API_BASE}/points/{formatted_lat},{formatted_lon}"
    points_data = await make_nws_request(points_url)
    
    if not points_data:
        return "Failed to get gridpoint: No response from API"
    if "error" in points_data:
        return f"Failed to get gridpoint: {points_data['error']}"
    if not points_data.get("properties"):
        return "Invalid gridpoint response: Missing properties"

    # Get forecast URL from properties
    forecast_url = points_data["properties"].get("forecast", "")
    if not forecast_url:
        return "No forecast URL found in gridpoint response"
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Failed to get forecast: No response from API"
    if "error" in forecast_data:
        return f"Failed to get forecast: {forecast_data['error']}"
    
    # Format the forecast data
    periods = forecast_data.get("properties", {}).get("periods", [])
    forecasts = []
    for period in periods[:5]:
        forecast = f"""
                        {period["name"]}:
                        Temperature: {period["temperature"]}°{period["temperatureUnit"]}
                        Wind: {period["windSpeed"]} {period["windDirection"]}
                        Forecast: {period["detailedForecast"]}
                    """
        forecasts.append(forecast)
    return "\n---\n".join(forecasts)


if __name__ == "__main__":
    mcp.run(transport="stdio")
