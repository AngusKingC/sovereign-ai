# Marine Weather Skill

## Name
Marine Weather

## Purpose
Fetch and summarize marine weather forecasts (wind, waves, precipitation, visibility) for a given lat/lon box.

## Inputs
- lat (float): latitude
- lon (float): longitude
- days (int, default 7): forecast horizon

## Outputs
Structured forecast summary (JSON) with per-day wind speed/direction, wave height, precipitation, visibility.

## Data Source
Open-Meteo Marine API (free, no API key required)
- Marine: `https://marine-api.open-meteo.com/v1/marine`
- Weather: `https://api.open-meteo.com/v1/forecast`

## Rate Limits
10,000 calls/day (free tier)

## Caching
30-minute TTL (weather doesn't change faster)

## Error Handling
If API unreachable, return last cached forecast + WARNING trace event.

## Approval Gate
NOT required (read-only, no side effects)

## Example Invocation
`marine_weather --lat 1.3521 --lon 103.8198 --days 7`
