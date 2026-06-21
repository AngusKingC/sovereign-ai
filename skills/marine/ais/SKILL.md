# AIS Vessel Tracker Skill

## Name
AIS Vessel Tracker

## Purpose
Query AIS (Automatic Identification System) data for vessel positions within a bounding box.

## Inputs
- min_lat (float): minimum latitude
- max_lat (float): maximum latitude
- min_lon (float): minimum longitude
- max_lon (float): maximum longitude

## Outputs
List of vessels with MMSI, name, lat, lon, speed, heading, timestamp.

## Data Source
AISHub (requires API key — user must provide via env var `AISHUB_API_KEY`)
- Endpoint: `http://data.aishub.net/ws.php?username={KEY}&format=1&output=json&compress=0&latmin={min_lat}&latmax={max_lat}&lonmin={min_lon}&lonmax={max_lon}`

## Security Note
AISHub does not offer HTTPS as of writing (2026-06). The API key is sent as a plaintext query parameter over HTTP. This is a known limitation of the upstream service, not a project defect. When a HTTPS endpoint becomes available, switch to it. Do not log the API key or vessel MMSIs in trace events — only counts.

## Rate Limits
Per AISHub plan (free tier: 5 queries/hour)

## Caching
60-second TTL (vessel positions update frequently)

## Error Handling
If API unreachable or no API key set, return empty list + WARNING trace event.

## Approval Gate
NOT required (read-only)

## Privacy
Do not log vessel names or MMSIs in trace events — only counts.
