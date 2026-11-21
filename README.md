# Envi Energy Probe

Read-only diagnostic companion to the unofficial Smart Envi integration for Home Assistant.

Current version: **0.1.4**.

Repository: https://github.com/rgerrans/Envi-Heater

This standalone Home Assistant integration uses domain `envi_energy_probe`. It does not replace or change Smart Envi's heater controls.

## What it does

- `envi_energy_probe.diagnose`: reports whether `smart_envi` / legacy `envi_heater` configurations and data sources are available.
- `envi_energy_probe.capture`: takes privacy-filtered snapshots from the Smart Envi coordinator cache, or read-only GET requests from the legacy API client. Supports baseline/heating comparisons in memory.
- **New in 0.1.4** — `envi_energy_probe.inspect_api`: retrieves the actual cloud API envelopes and device-list record shapes, plus live device details, **without returning raw records**. Uses the existing authenticated `smart_envi` client to make one `GET device/list` request and one `GET device/{id}` per selected heater.

The new action returns field names, field types, tightly allowlisted numeric/boolean/enum telemetry, and path differences between live device details and the coordinator cache. Sensitive subtrees, IDs, names, account details, credentials, token values, and arbitrary text are excluded. **The privacy filter is best-effort; review the response before sharing it.** Unknown or malformed keys are omitted. Large lists and deeply nested structures may be truncated and reported as such.

## Install or update with HACS

1. Add `https://github.com/rgerrans/Envi-Heater` as an **Integration** custom repository if not already added.
2. Find **Envi Energy Probe** in HACS and use **Redownload** with the `main` branch to install the latest commit (if HACS does not list a semantic version).
3. Restart Home Assistant.
4. Confirm `/config/custom_components/envi_energy_probe/manifest.json` has `"version": "0.1.4"`.
5. If this is a first-time installation, add **Envi Energy Probe** under Settings → Devices & Services.

The probe requires the newer `smart_envi` installation for `inspect_api`; the legacy `envi_heater` installation remains supported by `capture`.

## Run the new API inspector

In **Developer Tools → Actions**, switch to YAML mode:

```yaml
action: envi_energy_probe.inspect_api
data:
  unit: 1
```

To inspect all heaters, remove `unit`:

```yaml
action: envi_energy_probe.inspect_api
data: {}
```

The action makes read-only requests on invocation, **not continuous polling**, and never sends heater-control commands. It uses only the known endpoints `device/list` and `device/{id}`; it does not guess API paths or inspect unrelated accounts.

## Baseline versus heating

Capture a baseline with the heater on but its setpoint below ambient:

```yaml
action: envi_energy_probe.capture
data:
  phase: baseline
  unit: 1
```

After verifying that the same heater is physically heating and allowing a fresh data update:

```yaml
action: envi_energy_probe.capture
data:
  phase: heating
  unit: 1
```

The baseline is stored only in memory and is lost on probe reload/restart. Heater unit numbers refer to the current coordinator device ordering; do not rely on them as permanent identifiers.

## Limits

This tool does **not** measure watts, kWh, heater relay state, or power consumption. The presence of a suggestive field does not establish its meaning. The API is unofficial and may change without notice. A successful coordinator refresh does not prove a physical heater is energized.

## Removal

Remove Envi Energy Probe under Settings → Devices & Services, uninstall it through HACS, then restart. The Smart Envi control integration is not modified.
