# Envi Energy Probe

A temporary, **read-only** Home Assistant custom integration to inspect data already cached by [wlatic/envi_heater](https://github.com/wlatic/envi_heater).

- Separate Home Assistant domain: `envi_energy_probe`, so it does not replace or modify `smart_envi`.
- Reuses the existing Smart Envi coordinator cache. **No new login, polling, or heater commands.**
- Registers `envi_energy_probe.capture`, a response-only action under **Developer Tools → Actions**.
- Reports sanitized field paths and safe scalar values, and compares a stored baseline with a later heating sample.
- Supports multiple heaters; optional one-based `unit` index selects a single heater.

## Install with HACS

1. In HACS, open the menu → **Custom repositories**.
2. Add **https://github.com/rgerrans/Envi-Heater** with type **Integration**.
3. Search HACS for **Envi Energy Probe**, install, then restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **Envi Energy Probe**. Your existing Envi Smart Heater integration must be running.
5. Go to **Developer Tools → Actions** and run `envi_energy_probe.capture` with `phase: baseline`.

## Compare heater states

1. Choose a heater and set its target below room temperature while keeping the heater enabled. Allow 30–60 seconds for the existing integration to poll. Verify the heating element is no longer heating.
2. Capture `phase: baseline`, optionally setting `unit` to the heater's 1-based index.
3. Raise its target temperature above room temperature. Verify actual heating begins and allow another 30–60 seconds for the next poll.
4. Capture `phase: heating` using the same `unit` selection, then examine `changed_values_since_baseline`.
5. Share **reviewed, redacted** action responses for analysis. Field-name filtering is best-effort; unknown API fields could still contain sensitive information.

The probe **does not measure electricity**. Thermostat state and temperature changes do not establish element wattage. The baseline is held only in memory and is lost on restart or reload.

## Removal

Remove the Envi Energy Probe integration, uninstall it from HACS, and restart. Your `smart_envi` integration stays intact.

## Test status

Prototype version **0.1.1**. The earlier package was exercised with simulated Home Assistant objects; this GitHub publication has **not yet been verified on your Home Assistant host or live heaters**. Changes to the original integration's internal coordinator layout could make this diagnostic unavailable.
