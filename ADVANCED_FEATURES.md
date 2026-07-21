# Advanced Features

This page documents integration features that go beyond the basic entity tables in [README.md](README.md) — things that are easy to overlook, easy to misunderstand, or only relevant to specific hardware configurations.

## Integration Options

Beyond the initial setup, this integration has an **Options** flow: go to **Settings → Devices & Services → Luxtronik → Configure** to reach it. It lets you change, after setup and without removing/re-adding the integration:

- **External indoor temperature sensor** — replaces the heat pump's own room-thermostat reading (`Room Thermostat Temperature`) as the *current temperature* shown on the Heating climate entity, if you have a more accurate HA temperature sensor elsewhere in the house.
- **External power consumption sensor** — see [COP calculation](#cop-calculation-and-the-external-power-sensor) below.
- **Update interval** — how often the integration polls the heat pump for new data.

## DHW Manual Frequency (Matching Compressor Power to Solar Surplus)

The **DHW Manual Frequency** Number entity (Config category, enabled by default, 0–120 Hz) forces the compressor to run at a fixed frequency while heating DHW, instead of letting the heat pump's own control logic choose it:
- **`0` = Automatic** — the heat pump picks the frequency itself (the normal/default behavior).
- **`20`–`120` Hz** — the compressor is forced to run at (approximately) that fixed frequency for the whole DHW heating cycle.

Because a modulating compressor draws roughly proportionally less power at a lower frequency, this can be used for solar self-consumption: setting a **lower** frequency than the heat pump would have chosen on its own draws less instantaneous power, but takes correspondingly **longer** to reach the DHW target temperature. That lets a DHW charge track a modest, steady solar surplus for a longer stretch of time instead of the heat pump defaulting to a short, higher-power burst that could exceed what your panels are producing and pull the difference from the grid.

Two things worth knowing before relying on this:
- **The actual frequency can land about 1 Hz below whatever you set.** This was confirmed empirically and discussed at length in [GitHub issue #674](https://github.com/BenPru/luxtronik/issues/674) — if you need to verify the real value, compare against the **Pump Frequency** sensor during a DHW run rather than trusting the setpoint alone.
- **Remember to set it back to `0` (Automatic)** once you no longer have a surplus to chase — leaving a low fixed frequency in place on a cloudy day will make DHW heating take unnecessarily long, or fail to comfortably keep up with demand.

## Heating Circuit Control Mode (Bypassing the Heating Curve)

The **Heating circuit control mode** select entity (`select.<prefix>_heating_control_circuit_mode`, disabled by default, Config category) lets you change *how* the heat pump decides its flow/return target temperature for heating, with three options:
- **Heating curve control - Controlled by outside temperature** (the normal/default mode): the heat pump calculates its own target from the heating curve parameters and current outdoor temperature — this is what the rest of this README assumes.
- **Manual set temperature**: ignores the heating curve and outdoor temperature entirely, and instead uses a fixed target you set yourself via the **Manual target flow out temperature** Number entity (also disabled by default, 20–70°C).
- **Analog in**: the target is driven by an external analog input wired to the controller — not further configurable from Home Assistant.

This exists specifically for setups **without a room thermostat** that want to run the heat pump at a fixed flow/return temperature and build their own control logic on top (e.g. adjusting the manual target based on an indoor sensor and available solar power), instead of relying on the built-in outside-temperature-based curve. See [GitHub issue #482](https://github.com/BenPru/luxtronik/issues/482) for the original request and discussion this was built from.

A few things worth knowing before using it:
- **The Manual target flow out temperature (Number) and the Flow out target temperature (Sensor) are two different parameters.** The Number entity is what you write; the Sensor is the heat pump's own *calculated* current target, and it only catches up once the heat pump re-evaluates internally on its next poll (default every 60s — see [Integration Options](#integration-options) to poll faster if you need quicker feedback while testing). Seeing the sensor lag behind right after a change, or right after switching modes, is expected, not a sync bug.
- **The heat pump still enforces its own configured maximum flow temperature** (set on the physical/installer panel) regardless of what you request through the Number entity — so this cannot push the system past whatever ceiling was configured during commissioning.
- Because this fully replaces the built-in heating-curve regulation, treat it like the heating-curve parameters elsewhere in this README: avoid changing it frequently or aggressively via automations, since heat pumps are slow-reacting systems.

## Room Thermostat (RBE) Type and What "Target Temperature" Means

The Heating and Cooling climate entities' **Target Temperature** field does not always mean "desired room temperature" — what it actually controls depends on which room control unit (if any) is connected, detected from firmware parameter `P0033` (and, for RBE units specifically, the RBE's own firmware version):

| Detected type | Heating Target Temperature | Cooling Target Temperature |
| :--- | :--- | :--- |
| None / RFV / RFV-K / RFV-DK / RBE older than firmware 2.0 | A **correction offset**, −5…+5 °C, added to the heating curve — the same value as the **Target Temperature Correction** Number entity. Not an absolute room temperature. | The **Minimal Outdoor Temperature** threshold that must be exceeded before cooling is allowed to run at all — an outdoor-air value, not a room or water temperature. |
| RBE firmware 2.0+ ("RBE Plus"), or a directly reported "Smart" room unit | An actual **absolute desired room temperature**, read from and written to the room control unit itself. | Same absolute room-temperature parameter as Heating above — heating and cooling share one target, since both are driven by the same physical room unit. |

In other words: with an older/no room control unit, moving the Heating climate card's target temperature is really nudging the *heating curve* up or down by a few degrees (exactly like the **Target Temperature Correction** Number entity, because it's the same parameter), and the Cooling card's target temperature is really setting the *outdoor temperature* cooling waits for, not a room or flow temperature. Only a newer RBE ("RBE Plus", firmware ≥ 2.0) or a "Smart" room unit turns these into genuine room-temperature setpoints.

There is currently no dedicated entity showing which type your system has been detected as. To check it yourself, look at parameter `P0033` (`room_thermostat_type`) in a [diagnostics download](#diagnostics-download) — `0`/`1`/`2`/`3` are None/RFV/RFV-K/RFV-DK, `4` is RBE (check the RBE firmware version reported alongside it to tell old RBE from RBE Plus), and `5` is "Smart". The **Room Thermostat Temperature** and **Room Thermostat Target** sensors (if visible on your Heating device at all) confirm *some* room unit is connected, but not which behavior applies.

## COP Calculation and the External Power Sensor

The **Heating COP** and **DHW COP** sensors show an instantaneous coefficient of performance: current heat output divided by current power consumption. They only report a value while the heat pump is actively serving that circuit — otherwise they go `unavailable`, rather than show a stale or misleading ratio.

By default the power consumption figure (the denominator) comes from the heat pump's own reading, which is not always accurate. In **Integration Options** you can point the *external power consumption sensor* setting at a separate Home Assistant power sensor (e.g. a smart plug or clamp meter monitoring the outdoor unit) instead. Two things this does **not** do:
- It does not change what the regular "Current Power Consumption" sensor displays — only the COP calculation's denominator.
- It does not affect the heat output (numerator) side of the calculation, which always comes from the heat pump itself.

## EVU / Grid-Lock Status

Many installations (mainly in Germany/Austria) let the electricity utility (EVU, *Energieversorgungsunternehmen*) force the compressor into a lockout for a period, in exchange for a cheaper tariff. When this happens, the **Status** sensor's text briefly shows a cryptic-looking suffix, e.g. `EVU until 42 min` while a lockout is active, or `EVU in 15 min` when one is about to start within the next 30 minutes. This is expected behavior, not a fault.

The integration learns these lockout windows by observing the heat pump's own operating-mode transitions over time (it does not read a pre-configured EVU schedule from the controller) — so right after a Home Assistant restart, no EVU timing is known yet until at least one lockout has been observed. Once learned, the Status sensor also exposes extra attributes: first/second daily start and end time, which days of the week a lockout has been observed on, and minutes until the next event.

**Smart Grid Status** is a related but separate sensor: it only reports a value while the *Smart Grid* switch (see [Smart Grid & Power Limitation](#smart-grid--power-limitation) below) is enabled, and shows one of four SG-ready states (`EVU locked` / `Reduced operation` / `Normal operation` / `Increased operation`) derived from the heat pump's two EVU input signals.

## Firmware Update Entity

The **Firmware** update entity checks Alpha Innotec's public download portal (once per hour) for a newer firmware build than the one currently installed, comparing versions semantically. If a newer version exists, its release notes panel shows: a link to the manufacturer's firmware page for your specific model, a direct download link, localized (German/English) update instructions, and the raw change log fetched from the portal.

This entity is informational only — applying a firmware update is a manual, out-of-band process on the physical controller (typically via USB); the integration does not push or install firmware itself.

Because many entities in this integration are only created when the connected hardware reports the corresponding feature as present, *or* when the firmware version meets that entity's minimum requirement, a firmware update can unlock previously-missing sensors and controls without any changes on the Home Assistant side. If an entity documented in README or here doesn't show up on your system, check whether a newer firmware version is available before assuming it isn't supported.

## Diagnostics Download

Home Assistant's built-in **Download diagnostics** action (from the integration's device page, or Settings → Devices & Services → Luxtronik → the "..." menu) produces a redacted dump containing:
- every currently-known `parameter`, `calculation`, and `visibility` value read from the heat pump (name + raw value),
- device info,
- a partially-masked MAC address (only the vendor prefix is kept),
- the integration's own **recent log records** (see below).

This is the most useful thing to attach to a bug report or support request, since it captures the exact raw values the integration saw at that moment, without needing you to manually list them.

### Log records in diagnostics

The diagnostics dump also embeds the last ~1000 log lines this integration itself has logged (`log_records`), so you don't need to separately enable debug logging, reproduce, and download a system log file just to attach it to a bug report — one diagnostics download covers both.

This works by keeping an in-memory ring buffer attached directly to the integration's logger (see [log_capture.py](custom_components/luxtronik2/log_capture.py)), populated from the moment Home Assistant loads the integration. A few things worth knowing:
- It only ever contains what your logging configuration already let through. If you haven't enabled debug logging for this integration, the buffer mostly contains warnings/errors, not the detailed `LOGGER.debug(...)` trace most bug reports actually need — **enable debug logging, reproduce the issue, then download diagnostics**, in that order.
- Because a restart re-loads the integration (and the buffer) from scratch, this also captures **startup-time** problems, as long as debug logging was already enabled *before* the restart that reproduces them.
- The configured host/IP is scrubbed from log lines before being included (replaced with `**REDACTED_HOST**`), the same way the rest of the diagnostics payload is redacted. This is a best-effort, targeted substitution — not full log redaction — so still skim the download before posting it publicly if you're unsure.

## Away / Holiday Scheduling

Heating and DHW each have a pair of **Date** entities (Away/Holiday Start Date and End Date), settable independently for each circuit. The underlying firmware parameter names are symmetric — `Fstd` (*Ferien-Start-Datum*, holiday start date) and `Frkd` (*Ferien-Rückkehr-Datum*, holiday return date) — which means this isn't just an end-date safety net: you can set a **future** start date and the heat pump will switch itself into Holiday mode on that date and automatically switch back to Automatic on the return date, with no manual mode change needed on either end. This lets you pre-schedule an entire vacation period in advance.

This is in addition to the *Mode* select/water heater entities documented in README, which switch straight to Holiday mode immediately. Because heating and DHW have separate date pairs, you can schedule DHW's holiday period (e.g. while away) without also disabling space heating, or vice versa.

> **ℹ️ Note:** The exact interaction between an in-progress manual mode change and a still-pending scheduled date hasn't been verified against a physical unit; if you rely on this for unattended scheduling, check the *Mode* entity's actual state once the start date arrives.

## Second Heat Generator (Backup Electric Heater)

Two config entities (disabled by default, category *Configuration*) control when the secondary/backup heat generator — typically an electric immersion heater — is allowed to assist the heat pump:
- **Release Second Heat Generator**: the outdoor temperature (range −20…20 °C) below which the backup heater is allowed to engage.
- **Release Time Second Heat Generator**: how long (20–120 minutes) the heat pump must be unable to keep up before the backup heater is allowed to kick in.

Both entities — and the **Additional Heat Generator** running-state binary sensor — only appear if your unit reports having a second heat generator installed. Setting the temperature threshold too high, or the delay too short, causes the backup heater to engage more often than necessary, increasing electricity cost; setting them too conservatively risks insufficient heat output during cold snaps.

## Defrost (De-icing)

Air-source heat pumps periodically defrost their outdoor unit by briefly reversing the refrigerant cycle. Two binary sensors reflect this: **Defrost Valve** (the reversing valve is open) and **Defrost End / Flow OK** (the defrost cycle completed with acceptable flow). Seeing these toggle, or the heat pump's Status sensor briefly showing "Defrost", is normal periodic behavior on air/water systems — not a fault — and typically lasts a few minutes.

## Solar Thermal Collector

If your system has an integrated **solar thermal collector** feeding the DHW tank (not to be confused with solar PV / electricity generation, which this integration doesn't monitor directly), several entities appear under the DHW device once the heat pump reports a collector is present:
- **Solar Collector** / **Solar Buffer** temperature sensors,
- **Solar Pump** running-state binary sensor and its operating-hours counter,
- Configuration numbers for the solar pump's on/off temperature-difference thresholds (collector vs. tank) and the maximum collector temperature.

## PV Mode Selector

The **PV Mode** select entity (disabled by default) controls how the heat pump reacts to a PV (solar electricity) surplus signal, with options `Automatic`, `PV Off`, `Pool Off`, `Pool Party`, and `Pool Holidays`. This is separate from the Heating/DHW *Mode* selects already documented in README, and separate from the Solar Thermal Collector entities above — it specifically governs pool behavior tied to a PV surplus input, not the heat pump's general operating mode.

## Smart Grid & Power Limitation

- **Smart Grid** (switch, config category): enables/disables the heat pump's SG-ready integration as a whole. When on, the **Smart Grid Status** sensor (see [EVU / Grid-Lock Status](#evu--grid-lock-status)) becomes available.
- **Power limitation** / **Max. thermal power** (switches, disabled by default): turn on enforcement of the numeric power-limit entities below them (electrical power limit value; thermal power limits for heating/water/cooling) — the switches gate whether the limits are enforced at all, the number entities set the actual limit values.

Like the heating-curve parameters mentioned in README §3.2, these are typically set once during commissioning; avoid toggling them frequently via automations.
