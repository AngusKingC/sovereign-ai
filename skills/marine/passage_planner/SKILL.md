# Passage Planner Skill

## Name
Passage Planner

## Purpose
Plan a sailing passage between two waypoints, considering weather, tides, and vessel characteristics.

## Inputs
- start (lat, lon): departure waypoint
- end (lat, lon): destination waypoint
- vessel_speed (knots, default 6): average cruising speed
- departure_time (datetime): earliest departure

## Outputs
Passage plan with waypoints, ETA, weather windows, tidal constraints.

## Data Source
Aggregates weather (marine_weather skill), tidal (marine_tidal skill), and optional AIS (marine_ais skill).

## Dependencies
Calls marine_weather, marine_tidal skills; optionally calls marine_ais.

## Algorithm
1. Calculate great-circle distance and bearing
2. Fetch weather along route (sample every 50nm)
3. Fetch tides at start/end points
4. Identify weather windows (wind < 25 knots, waves < 2m)
5. Output plan with recommended departure window

## Approval Gate
NOT required for planning (read-only aggregation). If the plan triggers an action (e.g. "send to chart plotter"), that action would require approval.

## Limitation
v1 is advisory only — does not account for current, leeway, or vessel-specific polars. Documented here.
