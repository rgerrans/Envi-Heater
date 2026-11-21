"""Conservative, read-only Envi response-shape inspection helpers.

This module intentionally never returns raw API records, IDs, credentials,
unrestricted strings, or location/account identifiers.
"""
from __future__ import annotations

import math
import re
from typing import Any

# Exclude entire sensitive subtrees, not just scalar values.
PRIVATE_TERMS = (
    "token", "password", "secret", "auth", "credential", "cookie",
    "apikey", "api_key", "username", "email", "account", "serial",
    "ssid", "mac", "address", "location", "latitude", "longitude",
    "phone", "wifi", "network", "user_id", "device_id", "deviceid",
    "ip_address", "ipaddress", "uuid", "imei", "owner", "name",
    "room", "home", "zip", "postal", "geofence", "user", "identifier",
    "hardware_id", "pairing", "latitude", "longitude", "coordinate",
)
SENSITIVE_SEGMENTS = {"id", "key", "ip", "lat", "lon", "lng", "uid", "mac"}
CANDIDATES = (
    "power", "pow", "watt", "energy", "kwh", "wh", "heat", "stage",
    "relay", "runtime", "run_time", "consum", "state", "mode", "demand",
    "output", "running", "active", "duty", "element", "current",
    "temperature", "load", "status", "volt", "amp", "usage", "cycle",
    "level", "online", "runtime", "capacity", "standby", "fan",
)
# Whitelist is deliberate: even short strings can contain identifying data.
SAFE_ENUMS = {
    "on", "off", "heat", "heating", "cool", "cooling", "idle",
    "auto", "manual", "active", "inactive", "enabled", "disabled",
    "running", "stopped", "online", "offline", "high", "low",
    "half", "full", "standby", "ready", "success", "error",
    "true", "false", "open", "closed", "unknown", "eco",
}
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
NUMBER_RE = re.compile(r"^-?(?:0|[1-9]\d{0,7})(?:\.\d{1,4})?$")
MAX_DEPTH = 8
MAX_PATHS = 350
MAX_VALUES = 100
MAX_LIST_ITEMS = 6


def _sensitive(path: str) -> bool:
    tokens = re.sub(r"\[\d+\]", "", path).lower().split(".")
    for token in tokens:
        if (
            token in SENSITIVE_SEGMENTS
            or token.endswith("_id")
            or any(term in token for term in PRIVATE_TERMS)
        ):
            return True
    return False


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    return "other"


def _candidate_value(path: str, value: Any) -> Any:
    """Return an allowlisted telemetry scalar, or a sentinel for omitted data."""
    if not any(term in path.lower() for term in CANDIDATES):
        return _OMIT
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in SAFE_ENUMS:
            return lower
        if len(lower) <= 12 and NUMBER_RE.fullmatch(lower):
            return value.strip()
    return _OMIT


_OMIT = object()


def describe_structure(data: Any) -> dict[str, Any]:
    """Return only safe field paths, types, and tightly allowlisted telemetry.

    Arbitrary string values, dynamic/unusual keys and identifying subtrees are
    excluded. Truncation counts are included so absence isn't overinterpreted.
    """
    types: dict[str, str] = {}
    candidates: dict[str, Any] = {}
    excluded = 0
    truncated = False

    def walk(value: Any, path: str, depth: int) -> None:
        nonlocal excluded, truncated
        if depth > MAX_DEPTH or len(types) >= MAX_PATHS:
            truncated = True
            return
        if path:
            if _sensitive(path):
                excluded += 1
                return
            types[path] = _type_name(value)
            if len(candidates) < MAX_VALUES:
                safe = _candidate_value(path, value)
                if safe is not _OMIT:
                    candidates[path] = safe
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str) or not KEY_RE.fullmatch(key):
                    excluded += 1
                    continue
                walk(child, f"{path}.{key}" if path else key, depth + 1)
        elif isinstance(value, list):
            if len(value) > MAX_LIST_ITEMS:
                truncated = True
            for index, child in enumerate(value[:MAX_LIST_ITEMS]):
                walk(child, f"{path}[{index}]", depth + 1)

    walk(data, "", 0)
    return {
        "field_types": dict(sorted(types.items())),
        "candidate_values": dict(sorted(candidates.items())),
        "excluded_sensitive_or_unknown_key_count": excluded,
        "truncated": truncated,
    }


def envelope_types(response: dict[str, Any]) -> dict[str, str]:
    """Describe top-level keys only, keeping nested raw data private."""
    return {
        key: _type_name(value)
        for key, value in sorted(response.items())
        if KEY_RE.fullmatch(key) and not _sensitive(key)
    }


def structure_differences(live: dict[str, Any], cached: dict[str, Any]) -> dict[str, Any]:
    """Compare safely disclosed paths, never raw data or identifiers."""
    live_shape = describe_structure(live)
    cache_shape = describe_structure(cached)
    live_paths = set(live_shape["field_types"])
    cache_paths = set(cache_shape["field_types"])
    return {
        "new_paths_in_live_detail": sorted(live_paths - cache_paths),
        "paths_only_in_coordinator_cache": sorted(cache_paths - live_paths),
        "comparison_incomplete": live_shape["truncated"] or cache_shape["truncated"],
    }
