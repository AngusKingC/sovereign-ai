# Home Assistant Skill

## Description
Integrates with Home Assistant via REST API to control smart home devices and fetch entity states.

## Parameters
- entity_id (str, required): The entity ID to fetch or control
- domain (str, required): The service domain (e.g., "light", "switch")
- service (str, required): The service name (e.g., "turn_on", "turn_off")
- kwargs (dict, optional): Additional service parameters

## Output
- get_states(): Returns list of entity state dictionaries
- get_state(entity_id): Returns entity state dictionary
- call_service(domain, service, entity_id, **kwargs): Returns True on success

## Dependencies
- httpx>=0.24.0
- Home Assistant instance with REST API enabled
- Environment variables: HA_BASE_URL, HA_TOKEN

## Hardware
No special hardware requirements.

## Tags
home-automation, smart-home, rest-api, iot
