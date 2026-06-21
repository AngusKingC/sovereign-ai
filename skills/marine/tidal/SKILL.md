# Tidal Height Predictor Skill

## Name
Tidal Height Predictor

## Purpose
Predict tide heights and times for a given station and date range.

## Inputs
- station_id (str): NOAA station identifier
- start_date (date): forecast start
- end_date (date): forecast end

## Outputs
List of high/low tide events with timestamp and height (meters).

## Data Source
NOAA CO-OPS API (free, no API key)
- Endpoint: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station={STATION}&begin_date={YYYYMMDD}&end_date={YYYYMMDD}&product=predictions&datum=MLLW&units=metric&time_zone=gmt&format=json`

## Rate Limits
Per NOAA (generous, no documented limit)

## Caching
24-hour TTL (tide predictions are deterministic for future dates)

## Error Handling
If station_id invalid, return empty list + ERROR trace event.

## Approval Gate
NOT required (read-only)
