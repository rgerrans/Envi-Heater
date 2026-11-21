"""Read-only diagnostic companion to wlatic/envi_heater (smart_envi)."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from .const import DOMAIN, SOURCE_DOMAIN, SERVICE_NAME

PRIVATE_TERMS = (
    "token", "password", "secret", "auth", "credential", "cookie", "apikey",
    "api_key", "username", "email", "account", "serial", "ssid", "mac",
    "address", "location", "latitude", "longitude", "phone", "wifi",
    "network", "user_id", "device_id", "deviceid", "ip_address", "ipaddress",
    "uuid", "imei", "name", "owner", "room", "home",
)
CANDIDATE_TERMS = (
    "power", "watt", "energy", "kwh", "heat", "stage", "relay", "runtime",
    "run_time", "consum", "state", "mode", "demand", "output", "running",
    "active", "duty", "element", "current", "temperature", "percent",
    "load", "status", "volt", "amp", "usage", "level", "cycle",
)
MAX_DEPTH = 5
MAX_FIELD_PATHS = 250
MAX_VALUES = 150
MAX_STRING_LENGTH = 64

def _private_path(path: str) -> bool:
    """Exclude sensitive or identifying field names."""
    for part in path.lower().replace("[", ".").replace("]", "").split("."):
        if not part:
            continue
        if part in ("id", "key", "ip") or part.endswith("_id"):
            return True
        if any(term in part for term in PRIVATE_TERMS):
            return True
    return False

def _safe_string(value: str) -> bool:
    """Limit logging of unknown API strings."""
    if len(value) > MAX_STRING_LENGTH or not value:
        return False
    if any(s in value.lower() for s in ("http:", "https:", "@", "bearer ", "token", "password")):
        return False
    if re.search(r"\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b", value):
        return False
    if re.fullmatch(r"[0-9a-fA-F:-]{12,}", value):
        return False
    return True

def sanitize_device_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return paths and selected scalar values, not a raw API payload."""
    paths: list[str] = []
    values: dict[str, Any] = {}

    def visit(value: Any, path: str, depth: int) -> None:
        if depth > MAX_DEPTH or len(paths) >= MAX_FIELD_PATHS:
            return
        if path and not _private_path(path):
            paths.append(path)
        elif path:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(key, str) and len(key) <= 100:
                    visit(child, f"{path}.{key}" if path else key, depth + 1)
            return
        if isinstance(value, list):
            for i, child in enumerate(value[:8]):
                visit(child, f"{path}[{i}]", depth + 1)
            return
        if not path or len(values) >= MAX_VALUES:
            return
        if isinstance(value, bool):
            values[path] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value):
                values[path] = value
        elif value is None and any(t in path.lower() for t in CANDIDATE_TERMS):
            values[path] = None
        elif (
            isinstance(value, str)
            and any(t in path.lower() for t in CANDIDATE_TERMS)
            and _safe_string(value)
        ):
            values[path] = value

    visit(data, "", 0)
    return {"field_paths": sorted(set(paths)), "observed_values": dict(sorted(values.items()))}

def _coordinators(hass: HomeAssistant) -> list[Any]:
    """Find running coordinators of the original Smart Envi integration."""
    source_data = hass.data.get(SOURCE_DOMAIN)
    if not isinstance(source_data, dict):
        return []
    prefix = f"{SOURCE_DOMAIN}_coordinator_"
    return [
        coordinator for key, coordinator in source_data.items()
        if isinstance(key, str)
        and key.startswith(prefix)
        and callable(getattr(coordinator, "get_device_data", None))
        and isinstance(getattr(coordinator, "device_ids", None), list)
    ]

def read_cached_heaters(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Inspect cached records, never exposing Envi device IDs."""
    result: list[dict[str, Any]] = []
    index = 0
    for coordinator in _coordinators(hass):
        for device_id in coordinator.device_ids:
            index += 1
            device_data = coordinator.get_device_data(device_id)
            if not isinstance(device_data, dict) or not device_data:
                result.append({"unit": index, "available": False})
                continue
            result.append({
                "unit": index,
                "available": True,
                "coordinator_last_update_success": bool(coordinator.last_update_success),
                **sanitize_device_data(device_data),
            })
    return result

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register a response-only diagnostic action."""
    if not _coordinators(hass):
        raise ConfigEntryNotReady("Smart Envi must be running before the probe can attach")
    baseline: dict[int, dict[str, Any]] = {}

    async def capture(call: ServiceCall) -> dict[str, Any]:
        phase = call.data["phase"]
        unit = call.data.get("unit")
        snapshots = read_cached_heaters(hass)
        if not snapshots:
            raise HomeAssistantError("No Smart Envi devices available")
        if unit is not None:
            snapshots = [s for s in snapshots if s["unit"] == unit]
            if not snapshots:
                raise HomeAssistantError(f"Envi unit {unit} is not present")
        output = []
        for snap in snapshots:
            if not snap["available"]:
                output.append(snap)
                continue
            number = snap["unit"]
            now = snap["observed_values"]
            if phase == "baseline":
                baseline[number] = dict(now)
                snap["comparison"] = "Baseline saved in memory"
            elif number in baseline:
                before = baseline[number]
                snap["changed_values_since_baseline"] = {
                    key: {"baseline": before.get(key), "heating": now.get(key)}
                    for key in sorted(set(before) | set(now))
                    if before.get(key) != now.get(key)
                }
                snap["comparison"] = "Compared with most recent baseline"
            else:
                snap["comparison"] = "No baseline saved; capture phase=baseline first"
                snap["changed_values_since_baseline"] = {}
            output.append(snap)
        return {
            "phase": phase,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "Smart Envi coordinator cache (no extra API calls)",
            "note": "Capture time is not device update time; readings do not prove element power draw.",
            "heaters": output,
        }

    hass.services.async_register(
        DOMAIN, SERVICE_NAME, capture,
        schema=vol.Schema({
            vol.Required("phase"): vol.In(("baseline", "heating")),
            vol.Optional("unit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }),
        supports_response=SupportsResponse.ONLY,
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, SERVICE_NAME)
    return True
