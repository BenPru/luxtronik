# Reporting Issues

Found a bug, or something behaving unexpectedly? Please file it as a [GitHub Issue](https://github.com/BenPru/luxtronik/issues) on this repository. This page explains what to include so it can be diagnosed without a back-and-forth.

## Before opening an issue

1. Check the [Troubleshooting section](README.md#4-troubleshooting) in README first — connectivity issues are usually a heat pump restart or a missing static IP.
2. Search [existing issues](https://github.com/BenPru/luxtronik/issues?q=is%3Aissue) for your symptom; your heat pump model or firmware version may already be a known case.
3. Make sure you're on the **latest (beta) version** of the integration in HACS — the bug may already be fixed.

## What to include

A useful bug report needs one file plus a bit of context — no need to separately dig up system logs.

### 1. Diagnostics download (covers both state and logs)

1. Go to **Settings → Devices & Services → Luxtronik**, open the ⋮ menu, and choose **Enable debug logging**.
2. Reproduce the issue (trigger the automation, change the setting, restart Home Assistant if the issue happens at startup, etc.).
3. Go to **Settings → Devices & Services → Luxtronik**, open the device, and use **Download diagnostics** (⋮ menu).

This produces a single redacted JSON file containing every parameter/calculation/visibility value the integration currently has for your heat pump, device info, **and** the integration's own recent log records — so it captures both the exact raw state the integration saw *and* what happened while the bug occurred. See [Advanced Features: Diagnostics Download](ADVANCED_FEATURES.md#diagnostics-download) for exactly what it contains and what's redacted.

Step 1 (enabling debug logging) matters — without it, the embedded log records are mostly warnings/errors, not the detailed trace most bug reports need. If the bug only happens at startup, enable debug logging *before* the restart that reproduces it.

### 2. Context

Beyond that one file, please describe:
- **Heat pump model/manufacturer** (e.g. Alpha Innotec, Nibe, Novelan) and firmware version — both visible on the **Firmware** update entity, see [Advanced Features](ADVANCED_FEATURES.md#firmware-update-entity).
- **What you expected** vs. **what happened**, and the exact steps to reproduce.
- Whether the behavior is new (regression after an update) or has always been present.

## Privacy note

The diagnostics download redacts your host/IP, credentials, and unique identifiers, and only keeps the MAC address's vendor prefix (see `TO_REDACT` in [diagnostics.py](custom_components/luxtronik2/diagnostics.py)). The embedded log records have the same host/IP scrubbed out, but that's a targeted substitution, not full redaction — skim them before attaching if you're concerned about anything else sensitive appearing (this integration doesn't log credentials, but always worth a quick check).
