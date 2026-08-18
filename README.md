[![Release](https://img.shields.io/github/v/release/BenPru/luxtronik?label=latest-release&color=green&logo=github)](https://github.com/BenPru/luxtronik/releases/latest)
![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads/BenPru/luxtronik/latest/total)
[![Pre-release](https://img.shields.io/github/v/release/BenPru/luxtronik?include_prereleases&label=pre-release&color=orange&logo=github)](https://github.com/BenPru/luxtronik/releases)
![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads-pre/BenPru/luxtronik/latest/total?label=downloads@pre-release&color=orange)
![GitHub License](https://img.shields.io/github/license/benpru/luxtronik)


# Luxtronik Home Assistant Integration

This is a Home Assistant integration for [Luxtronik heat pumps](https://www.alpha-innotec.com/en/products/accessories/control/luxtronik).

It is based on [Bouni/luxtronik](https://github.com/Bouni/luxtronik) which provides the groundwork for this integration. This integration extends the Bouni integration with with predefined entities and a full UI setup. Bouni en BenPru can run side by side.

If you like this project, give it a ⭐, or sponsor the developers:
* Project creator: [BenPru](https://github.com/sponsors/BenPru).
* Current developer: [rhammen](https://github.com/sponsors/rhammen).

It takes a lot of time and effort to keep up with changes (Home Assistant and Luxtronik Firmware). BenPru has handed over the project to the community fos us to maintain. This means the project depends on you to submit issues and work with the community's developers to improve the integration. See [REPORTING_ISSUES.md](REPORTING_ISSUES.md) for how to file a bug report that's actionable on the first pass.

Big thanks to [all community members](https://github.com/BenPru/luxtronik/graphs/contributors) who have contributed to this project. 

## 📖 Contents

- [⚠️ Warning](#️-warning) — what you can break, and how the integration limits that
- [🔧 Compatibility](#-compatibility) — supported controllers and brands
- [1. Installation](#1-installation) — add the HACS repository, install, add your heat pump, configure options
- [2. Using Luxtronik](#2-using-luxtronik) — the devices and their entities
  - [2.1 Heatpump](#21-heatpump) · [2.2 Heating](#22-heating) · [2.3 Cooling](#23-cooling) · [2.4 DHW](#24-dhw-domestic-hot-water) (incl. [2.4.1 DHW Timer Schedule](#241-dhw-timer-schedule-blocking-times)) · [2.5 Ventilation](#25-ventilation)
- [3. Automations & Advanced Usage](#3-automations--advanced-usage)
  - [3.1 Common Automations](#31-common-automations) (incl. [3.1.1 Automating Cooling](#311-automating-cooling) and [3.1.2 Automating DHW](#312-automating-dhw)) · [3.2 Advanced Entities](#32-advanced-entities-configuration) · [3.3 Energy Use](#33-energy-use)
- [4. Troubleshooting](#4-troubleshooting) — first steps when something doesn't work

**Other documents in this repository:**

- **[ADVANCED_FEATURES.md](ADVANCED_FEATURES.md)** — integration options, COP and the external power sensor, EVU/Smart Grid, diagnostics downloads, holiday scheduling, solar thermal, and the other entities that only appear on some hardware.
- **[TIMER_SCHEDULES.md](TIMER_SCHEDULES.md)** — the editable weekly schedules for DHW, heating, and ventilation: entity list, time format, and what a window means on each circuit.
- **[REPORTING_ISSUES.md](REPORTING_ISSUES.md)** — how to file a bug report that can be diagnosed on the first pass.

## ⚠️ Warning
Some settings exposed by this integration can impact the performance of your heat pump. Misconfigurations may cause the controller to go into an error state, requiring a local manual reset. 

This project aims to protect your heat pump by limiting the configuration range to safe values. However, **no guarantees can be given**. Please be careful, consult your [Luxtronik manual](https://mw.ait-group.net/files/docs/EN/A0220/83055400.pdf), and avoid changing settings you do not fully understand.

## 🔧 Compatibility
The integration lets you monitor and control heat pump units containing a Luxtronik controller. It **works locally** without internet access. Just plugin the ethernet cable and you're good to go.  

It is used by manufacturers such as:
- Alpha Innotec, 
- Siemens, 
- Novelan, 
- Roth, 
- Elco, 
- Buderus, 
- Nibe, 
- Wolf Heiztechnik.


---

## 1. Installation

### Step 1: Add the repository to HACS

Click the button below to open the integration directly in HACS:

[![Open your Home Assistant instance and show the HACS repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BenPru&repository=Luxtronik&category=integration)

*(Alternatively: Open **HACS** > **Integrations**, search for **Luxtronik**, select it, and click **Download**).*

### Step 2: Install the Integration

1. Open HACS in Home Assistant.
2. In Home Assistant, go to **Integrations** -> **Explore & Download Repositories**.
3. Search for **Luxtronik**. Check that it's the BenPru integration by clicking on it. 
4. Click on the integration, then click **Download** at the bottom right.
5. **Restart** Home Assistant to load the new integration files.

### Step 3: Add the Luxtronik Device(s)

1. **Auto-discovery:** Home Assistant should automatically discover your heat pump. Check the **Settings -> Devices & Services** page and click **Configure**.
2. **Manual Addition:** If auto-discovery fails, click **Add Integration** in the bottom right corner, search for **Luxtronik**, and enter the IP address of your heat pump manually. *(Tip: Ensure the heat pump has a static IP in your router).*

### Step 4 (optional): Configure Integration Options

After setup, **Settings → Devices & Services → Luxtronik → Configure** lets you set an external indoor temperature sensor, an external power sensor for more accurate COP readings, and the polling interval. See [Advanced Features: Integration Options](ADVANCED_FEATURES.md#integration-options).

---

## 2. Using Luxtronik

Entities and actions are organized into up to five logical devices in Home Assistant to keep things structured. Here is an overview of what each device does and how to use the most common entities. *Cooling*, *DHW* and *Ventilation* only appear if the heat pump reports that capability; *Heatpump* and *Heating* are always present.

> **ℹ️ Note:** Not every entity documented below will exist on every installation. Each one is only created if your specific heat pump reports the corresponding feature as present (e.g. a solar collector, a second heat generator, cooling capability) or its firmware version meets that entity's minimum requirement. This means **updating your heat pump's firmware can make additional sensors and controls appear** in Home Assistant that weren't there before — if you're missing an entity mentioned here, check whether a firmware update is available (see [Advanced Features: Firmware Update Entity](ADVANCED_FEATURES.md#firmware-update-entity)) before assuming it's unsupported.
>
> A few entities — the pool heat and energy counters among them — are instead created only once their register reports something other than its idle value, because on a unit without that feature it never changes. This check runs when the integration starts, so if the feature is newly installed or has never run before, **restart Home Assistant or reload the integration** (Settings → Devices & Services → Luxtronik → ⋮ → Reload) once it has, to make those entities appear.

### 2.1 Heatpump
This device represents the physical heat pump unit. It contains sensors and diagnostic entities such as electrical power consumption, thermal power output, operating hours, and current status.

**Most important entities:**
- **Status:** Shows whether the heat pump is heating, cooling, making hot water, or idle. If your utility provider can force the compressor into a lockout period (EVU), the status text also briefly shows a countdown like "EVU until 42 min" — see [Advanced Features: EVU / Grid-Lock Status](ADVANCED_FEATURES.md#evu--grid-lock-status).
- **Power Consumption Sensors:** Ideal for tracking energy usage if your model supports it.
- **Errors/Lockouts:** Alerts if your heat pump is in an error state.
- **Firmware:** An Update entity that checks for newer firmware; see [Advanced Features: Firmware Update Entity](ADVANCED_FEATURES.md#firmware-update-entity).

> **ℹ️ Tip:** If you need to report a bug, use Home Assistant's built-in **Download diagnostics** action on this integration first — see [Advanced Features: Diagnostics Download](ADVANCED_FEATURES.md#diagnostics-download).

Depending on your hardware, you may also see PV-linked pool control, Smart Grid / power-limitation switches, or a second (backup) heat generator's settings on this device — see [Advanced Features](ADVANCED_FEATURES.md) for those.

### 2.2 Heating
This device controls the space heating functionality (e.g., underfloor heating or radiators).

**Most important entities & actions:**
- **Heating Climate Entity (`climate.heating`):** The primary thermostat to view the current operation mode and adjust the target temperature. **What "Target Temperature" actually means depends on your room control unit** — with an older/no room unit it's a −5…+5°C correction offset on the heating curve (same value as *Target Temperature Correction* below); with a newer RBE ("RBE Plus") or "Smart" room unit it's a real desired room temperature. See [Advanced Features: Room Thermostat (RBE) Type](ADVANCED_FEATURES.md#room-thermostat-rbe-type-and-what-target-temperature-means).
- **Heating Operation Mode:** Choose between Automatic, Second Heatsource, Party (boost), Holidays (reduced), or Off.
- **Target Temperature Correction:** Quickly bump the heating target up or down by a few degrees without altering the main heating curve.
- **Away/Holiday Start & End Date:** Pre-schedule a future Holiday period — the heat pump switches into Holiday mode on the start date and back to Automatic on the end date automatically — see [Advanced Features: Away / Holiday Scheduling](ADVANCED_FEATURES.md#away--holiday-scheduling).
- **Heating Circuit Control Mode** *(disabled by default)*: switches the heat pump between its normal outside-temperature heating curve and a fixed manual flow/return target temperature — useful if you don't have a room thermostat and want to build your own control logic. See [Advanced Features: Heating Circuit Control Mode](ADVANCED_FEATURES.md#heating-circuit-control-mode-bypassing-the-heating-curve).
- **Heating Timer Program & Heating Timer Schedule:** The controller's weekly schedule of **raise times** — windows in which the heating circuit runs in day mode, with night setback applying outside them — editable as Text entities, with a Select choosing the schedule shape (whole week / weekdays + weekend / per day). Note this is the opposite polarity from the DHW schedule's blocking times. See **[TIMER_SCHEDULES.md](TIMER_SCHEDULES.md)**.

### 2.3 Cooling
If your heat pump supports active or passive cooling, this device manages it.

Basic entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Cooling** | Climate | &deg;C | The climate entity combines several of the entities below into a combined climate entity. It shows the current temperature and controls the *Cooling Mode*. **Its Target Temperature field is not a room/water setpoint unless a newer RBE Plus or Smart room unit is connected** — with an older/no room unit it's actually the same value as the *Minimal Outdoor Temperature* entity below (an outdoor-air threshold). See [Advanced Features: Room Thermostat (RBE) Type](ADVANCED_FEATURES.md#room-thermostat-rbe-type-and-what-target-temperature-means) for the full breakdown. Note: Cooling does not aim for the target temperature the way heating does even in the room-temperature case. |
| **Cooling** | Select / Switch | on/off | Controls the state. "Off" disables cooling, while "On" allows cooling depending on the *Approval*, *Minimal Outdoor Temperature* and *Room Thermostat Target Temperature* entities. |
| **Approval** | Binary Sensor | - | Indicates if cooling is unlocked by the heat pump based on various factors such as outdoor temperature and room temperature. Consult the manual for more details |

Advanced entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Cooling Minimal Flow Temperature** | Number | &deg;C | The minimal water temperature used for activating cooling. Default 18&deg;C. |
| **Minimal Outdoor Temperature** | Number | &deg;C | The outdoor temperature threshold that must be exceeded before cooling is allowed to start. |
| **Start Delay** | Number | h | How long the outdoor temperature must stay above *Minimal Outdoor Temperature* before cooling actually starts (0–12h) — a debounce so a brief warm spell doesn't trigger cooling. **Bypassed entirely if the outdoor temperature exceeds the threshold by more than 5°C at once** — in that case cooling starts immediately regardless of this delay. |
| **Stop Delay** | Number | h | How long the outdoor temperature must stay back below *Minimal Outdoor Temperature* before cooling actually stops (0–12h) — prevents rapid on/off cycling right at the threshold. |

> **ℹ️ Note:** Cooling is always the lowest-priority demand on the heat pump — e.g. an active DHW heating demand will interrupt or block cooling regardless of how *Start Delay*/*Stop Delay*/*Minimal Outdoor Temperature* are set. If *Approval* never turns on despite the outdoor temperature clearly qualifying, check for a competing demand first.

> **⚠️ Important:** If the cooling target temperature is set too low, condensation can form on floor tiles, pipes, and inside the heat pump. A brine heat pump should generally not use a target temperature below 18°C to avoid damage. Consult your manual for details.

> **ℹ️ Note:** The Energy input may not work as expected. This is a limitation of the Luxtronik firmware.

The amount of cooling can be controlled with the Cooling climate entity's *Target Temperature* when the heatpump is configured to cool based on fixed temperature ([page 17](https://mw.ait-group.net/files/docs/EN/A0220/83055400.pdf)) — remember its meaning depends on your room control unit, per the note above.

**Automating cooling** has its own section further down: [§3.1.1 Automating Cooling](#311-automating-cooling).

### 2.4 DHW (Domestic Hot Water)
This device controls the boiler/tank for your tap water.

Basic entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Domestic Water** | Water Heater | °C | The water heater entity combines several of the entities below into a combined water heater entity. It shows the *Domestic Hot Water* temperature and allows setting the *Target* temperature. It has 4 operating modes (Automatic / Party / Holiday / Off). The away mode sets the operating *Mode* to Holiday or the last known state. |
| **Mode** | Select | - | Sets the operating *Mode*: Automatic / Party / Holiday / Off. Automatic is for standard operation. Party is for increased hot water. Holiday and Off suspend operations. |
| **Mode Automatic** | Switch | on/off | Sets the operating mode to Off or last known state. |
| **DHW Target Temperature** | Number | °C | Set the DHW target temperature. |
| **DHW Current Temperature** | Sensor | °C | The current DHW temperature. |

Advanced entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Hysteresis** | Number | °C | The difference between the *DHW Current Temperature* and *DHW Target Temperature* before the water is heated up gain to the *DHW Target Temperature*. |
| **Thermal Desinfection Target Temperature** | Number | °C | Target temperature for Thermal Disinfection cycle. |
| **Thermal Desinfection Day** | Select | Day | The day on which the thermal disinfection cycle is performed, or `continuous` to make every DHW heating cycle eligible (see the on-demand trick below). The heat pump runs the cycle at its own fixed nightly time on that day — this integration cannot change *when* it runs, only *which day(s)*. |
| **DHW Manual Frequency** | Number | Hz | Forces the compressor to a fixed frequency during DHW heating instead of the heat pump's own automatic choice (`0` = Automatic). Useful for solar self-consumption — see [Advanced Features: DHW Manual Frequency](ADVANCED_FEATURES.md#dhw-manual-frequency-matching-compressor-power-to-solar-surplus). |
| **Away/Holiday Start & End Date** | Date | - | Pre-schedule a future DHW Holiday period (auto start and return), independent of the Heating device's own dates — see [Advanced Features: Away / Holiday Scheduling](ADVANCED_FEATURES.md#away--holiday-scheduling). |
| **Hot water timer program** | Select | - | Which blocking-time schedule shape the controller uses: *Whole week*, *Weekdays + weekend*, or *Per day*. Switching it swaps which schedule entities are present — see [TIMER_SCHEDULES.md](TIMER_SCHEDULES.md). |

> **ℹ️ Note:** It is not possible to trigger a thermal disinfection cycle on demand, or move it off its fixed nightly time, using the *Thermal Desinfection Day* select alone. It can be emulated at a time of your choosing by temporarily setting *Thermal Desinfection Day* to `continuous` and raising the *DHW Target Temperature* to the *Thermal Desinfection Target Temperature* value — this makes the heat pump's normal (immediate) heating logic reach disinfection temperature right away, instead of waiting for its own nightly schedule. See the *Legionella prevention using solar power* example below. The **Thermal Desinfection Target Temperature** entity also exposes a `last_thermal_desinfection` timestamp attribute (last time the DHW temperature rose above that target), handy for gating an automation like the example to "at most once a week".

If your system has an integrated **solar thermal collector** feeding the DHW tank, extra temperature/pump entities appear automatically — see [Advanced Features: Solar Thermal Collector](ADVANCED_FEATURES.md#solar-thermal-collector).

#### 2.4.1 DHW Timer Schedule (Blocking Times)

DHW also supports an editable weekly schedule of **blocking times** — windows during which automatic DHW heating is switched off, exposed as a set of Text entities. The controller offers three schedule shapes (whole week, weekdays + weekend, per day) selected by the *Hot water timer program* entity; only the selected shape's schedule entities are present, the others are disabled. See **[TIMER_SCHEDULES.md](TIMER_SCHEDULES.md)** for the entity list, the `HH:MM-HH:MM/...` format, and an important note on how DHW's blocking-time semantics differ from the heating schedule.

**Automating DHW** has its own section further down: [§3.1.2 Automating DHW](#312-automating-dhw).

### 2.5 Ventilation

Some units have an integrated ventilation module (controlled ventilation with heat recovery). If yours does, a fifth device appears with the module's own sensors and controls.

Basic entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Ventilation mode** | Select | - | The module's operating mode: *Automatic* / *Party* / *Holidays* / *Off*. As on the heating circuit, the programmed timer schedule is expected to apply only in *Automatic* — see the note below. |
| **Supply air temperature** | Sensor | °C | Temperature of the air being supplied to the rooms. |
| **Exhaust air temperature** | Sensor | °C | Temperature of the air being extracted from the rooms. |
| **Supply fan setpoint** / **Exhaust fan setpoint** | Sensor | % | How hard each fan is currently being driven, as a percentage of its full analog output. These are modulating outputs, so the value tracks the active stage rather than just on/off. |

Advanced entities (diagnostic, read-only):
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Humidity protection stage** / **Reduced stage** / **Nominal stage** / **Intensive stage** | Sensor | m³/h | The four airflow rates configured on the controller for the DIN 1946-6 ventilation stages. They show how the module is commissioned, and let you interpret a fan setpoint: on a 400 m³/h unit, a *Nominal stage* of 250 m³/h corresponds to a 62.5 % fan setpoint. |

The module also has an editable weekly schedule (*Ventilation timer program* select + *Ventilation Timer Schedule* text entities) — see **[TIMER_SCHEDULES.md](TIMER_SCHEDULES.md)**, including which parts of its behaviour are still unconfirmed.

> **ℹ️ Note:** The stage entities are deliberately read-only sensors rather than writable Number entities: their scale (m³/h with no conversion) is established from a single system, and a wrong unit on a display is a cosmetic problem while a wrong unit on a write is not. Set the stages on the controller itself.

> **ℹ️ Note:** Whether this device exists is decided from the module's own air temperature readings, not from the controller's ventilation visibility flag — that flag reads 0 on units with a perfectly functional module, which would hide the device. The device is created when the integration starts, so after retrofitting a module, **reload the integration** (Settings → Devices & Services → Luxtronik → ⋮ → Reload) to make the device appear.

---

## 3. Automations & Advanced Usage

### 3.1 Common Automations

Here are a few practical examples of how to automate your Luxtronik heat pump:

**1. Boost hot water before taking a bath:**
Put the DHW circuit into *Party* mode when you need extra hot water quickly. There are two equivalent ways to do it, and in practice this is usually a **manual action in the UI** rather than an automation: either set the *Domestic water* water heater card to **Performance**, or set the *DHW mode* select to **Party**. Both write the same operating mode to the heat pump — use whichever entity is already on your dashboard.

It can of course be automated if you want it on a schedule or a trigger:
```yaml
# via the water heater entity
action: water_heater.set_operation_mode
target:
  entity_id: water_heater.luxtronik_domestic_water
data:
  operation_mode: performance

# ...or via the mode select
action: select.select_option
target:
  entity_id: select.luxtronik_dhw_mode
data:
  option: party
```
Remember to switch back to *Automatic* (water heater: **Heat pump**) afterwards — *Party* stays on until it is changed, and it overrides any [DHW blocking-time schedule](#241-dhw-timer-schedule-blocking-times) you have programmed.

**2. Reduce heating target while away:**
Use the target correction entity to temporarily lower the heating curve by 2 degrees when nobody is home.
```yaml
action: number.set_value
target:
  entity_id: number.luxtronik_heating_target_correction
data:
  value: -2.0
```

**3. Solar PV optimization (Simple):**
If your solar panels are producing excess energy, increase the DHW target temperature so the heat pump acts as a thermal battery.
```yaml
action: water_heater.set_temperature
target:
  entity_id: water_heater.luxtronik_dhw
data:
  temperature: 55
```

#### 3.1.1 Automating Cooling
It's important to understand your setup and configurations in order to correctly automate cooling using Home Assistant. A properly configured heatpump can work well on it's own and requires little intervention. 

It is not possible to force cooling to start. This is controlled by the heatpump based on the *Approval* and *Minimal Outdoor Temperature settings*. "Pausing" cooling can be done by switching *Cooling* to off. 
<details>
<summary>⚙️ Example: Cooling using solar power</summary>
```yaml
description: "Toggle Luxtronik cooling based on solar power"
trigger:
  - platform: numeric_state
    entity_id: sensor.solar_power
    above: 200
    for: "00:10:00"
    id: "solar_high"
  - platform: numeric_state
    entity_id: sensor.solar_power
    below: 200
    for: "00:10:00"
action:
  - if:
      - condition: trigger
        id: "solar_high"
    then:
      - action: switch.turn_on
        target:
          entity_id: switch.luxtronik_cooling
    else:
      - action: switch.turn_off
        target:
          entity_id: switch.luxtronik_cooling
```
</details>

#### 3.1.2 Automating DHW
Automations for DHW typically use the water heater entity or the Party/Boost mode. Common scenarios include pre-heating before showers, using excess solar energy to heat the tank.

<details>
<summary>⚙️ Example: Preheat DHW using solar power</summary>
```yaml
description: "Boost DHW when solar production is high"
trigger:
  - platform: numeric_state
    entity_id: sensor.solar_power
    above: 2000
    for: "00:05:00"
    id: "solar_high"
  - platform: numeric_state
    entity_id: sensor.solar_power
    below: 2000
    for: "00:10:00"
action:
  - if:
    - condition: trigger
      id: "solar_high"
    then:
      - action: water_heater.set_temperature
        target:
          entity_id: water_heater.luxtronik_dhw
        data:
          temperature: 58
    else:
      - action: water_heater.set_temperature
        target:
          entity_id: water_heater.luxtronik_dhw
        data:
          temperature: 54
```
</details>

<details>
<summary>⚙️ Example: Legionella prevention (thermal disinfection) using solar power instead of midnight</summary>

The heat pump's built-in thermal disinfection cycle always runs at a fixed nightly time on whichever *Thermal Desinfection Day* is configured — there's no entity to change *when* it runs. This automation instead triggers a disinfection-grade heating cycle around midday, when solar production is typically highest, by temporarily switching *Thermal Desinfection Day* to `continuous` and raising the *DHW Target Temperature* to the disinfection target — which makes the heat pump's normal, immediate heating logic do the work instead of waiting for the nightly schedule. It uses the `last_thermal_desinfection` attribute (on the *Thermal Desinfection Target Temperature* entity) to only run once a week, and reverts both settings afterwards so normal DHW operation resumes.

> **ℹ️ Note:** The weekly-gate condition treats a never-yet-recorded `last_thermal_desinfection` (i.e. its value is empty/unknown) as "overdue," not "skip." If you built this before ever running it once, `last_thermal_desinfection` starts out empty and stays that way until the very first successful run — an `and`-style condition that *requires* a real timestamp before proceeding would never let that first run happen at all.

```yaml
alias: "Legionella prevention using solar power"
description: "Run thermal disinfection around midday to use solar power, instead of the heat pump's fixed nightly schedule"
trigger:
  - platform: time
    at: "11:45:00"
condition:
  - condition: state
    entity_id: select.luxtronik2_dhw_mode
    state: "automatic"
  - condition: template
    value_template: >
      {% set last = state_attr('number.luxtronik2_dhw_thermal_desinfection_target', 'last_thermal_desinfection') %}
      {{ last in [None, 'unknown', 'unavailable', ''] or
         (as_timestamp(now()) - as_timestamp(last)) > (7 * 24 * 3600) }}
action:
  - action: select.select_option
    target:
      entity_id: select.luxtronik2_thermal_desinfection_day
    data:
      option: "continuous"
  - delay:
      seconds: 10
  - action: number.set_value
    target:
      entity_id: number.luxtronik2_dhw_target_temperature
    data:
      value: 57  # match your Thermal Desinfection Target Temperature
  - wait_for_trigger:
      - platform: numeric_state
        entity_id: sensor.luxtronik2_dhw_temperature
        above: number.luxtronik2_dhw_thermal_desinfection_target
        for:
          minutes: 1
    timeout:
      hours: 5
  - action: select.select_option
    target:
      entity_id: select.luxtronik2_thermal_desinfection_day
    data:
      option: "none"
  - delay:
      seconds: 10
  - action: number.set_value
    target:
      entity_id: number.luxtronik2_dhw_target_temperature
    data:
      value: 50  # restore your normal DHW target temperature
```

> **ℹ️ Note:** The `57`/`50` values above must match your own *Thermal Desinfection Target Temperature* and normal *DHW Target Temperature* settings. The `wait_for_trigger` has a 5-hour timeout so the automation still reverts the temporary settings even if the target is never reached (e.g. insufficient solar that day).

</details>

### 3.2 Advanced Entities (Configuration)

To protect your system from accidental misconfiguration, several advanced configuration parameters are **disabled by default**. They can be enabled manually from the Home Assistant entity registry if you need them.

**These advanced entities include:**
- **Thermal & Electrical Power Limits:** Switches gate whether power limiting is enforced at all; separate Number entities set the actual limit values. Used to throttle the heat pump's maximum power output. See [Advanced Features: Smart Grid & Power Limitation](ADVANCED_FEATURES.md#smart-grid--power-limitation).
- **Heating Curve Parameters:** (End temperature, Parallel shift, Night offset) These define how the heat pump reacts to outdoor temperatures. They are typically configured once during commissioning by your installer. Use [mnemotron.de's heating curve visualizer](https://mnemotron.de/lux/heatcurve.html) to plot the exact resulting curve for your parameter values before changing them.
- **Heating Threshold Temperature:** The outdoor temperature above which the heating completely stops.
- **Second Heat Generator Settings:** The outdoor temperature and delay that determine when the backup electric heater is allowed to engage. See [Advanced Features: Second Heat Generator](ADVANCED_FEATURES.md#second-heat-generator-backup-electric-heater).
- **Smart Grid / PV Mode:** Controls tied to SG-ready and PV-surplus signals — see [Advanced Features](ADVANCED_FEATURES.md#smart-grid--power-limitation).

> **Tip:** Do not modify the heating curve or power limits frequently via automations. Heat pumps are slow-reacting systems and perform best when left running with stable parameters.

### 3.3 Energy Use

Not all heat pumps have built-in electrical energy metering. Some only show the thermal energy produced but not the electricity consumed. 
If you want to accurately measure the SCOP (Seasonal Coefficient of Performance) of your device, consider adding an external energy meter. Devices like Shelly offer a [16A power plug](https://www.shelly.com/en-nl/products/product-overview/1xplug) or [in-line/clamp energy meters](https://www.shelly.com/en-nl/products/energy-metering-energy-efficiency) that integrate perfectly with Home Assistant.

The **Heating COP** and **DHW COP** sensors report an instantaneous efficiency ratio, and can use such an external meter directly as their power-consumption input instead of the heat pump's own reading — see [Advanced Features: COP Calculation and the External Power Sensor](ADVANCED_FEATURES.md#cop-calculation-and-the-external-power-sensor).

**Pool heating** has its own pair of lifetime counters on the *Heatpump* device (diagnostic category): **Pool heat amount** — the thermal energy delivered to the pool — and **Pool energy input**, the electricity the heat pump consumed producing it. Both are total-increasing energy sensors in kWh, so Home Assistant keeps long-term statistics for them, and dividing one by the other over a period gives the pool circuit's seasonal efficiency. They are only created once their register reads something other than zero, because a unit without a pool reports 0.0 forever — so on a newly commissioned pool, reload the integration once it has run (see the note at the top of [§2 Using Luxtronik](#2-using-luxtronik)).

> **⚠️ Series-2 controllers (firmware V2.x): the Additional heat generator energy sensors now read ten times lower.**
> On a series-2 controller these counters step in 0.01 kWh, not the 0.1 kWh the integration previously assumed, so a unit that reported 14714 kWh now correctly reports 1471.4 kWh. Because they are total-increasing energy sensors, Home Assistant reads that one-off drop as a meter reset and books the first reading after the update as fresh consumption — a spurious spike of roughly the sensor's whole lifetime total in the energy dashboard.
> To remove it, open **Developer Tools → Statistics**, find each *Additional heat generator energy* sensor, and use the **Fix issue / adjust sum** action on the day the update landed. Series-3 controllers (V3.x) are unaffected; their scale was verified in #625 and has not changed.

---

## 4. Troubleshooting

In case of connectivity or data issues, please perform the following steps first:
1. **Restart the heat pump.** Perform a full power cycle by turning off the physical switch, waiting a few moments, and turning it back on. This solves most Luxtronik controller network issues.
2. Ensure the heat pump has a **Static IP address** configured in your router.
3. Update to the **latest (beta) version** of this integration in HACS.
4. If issues persist, enable debug logging for this integration and check the Home Assistant logs.

**Missing an entity mentioned in this README?** It may simply not be created for your unit — see the note at the top of [§2 Using Luxtronik](#2-using-luxtronik) about hardware- and firmware-gated entities, and consider checking for a firmware update.

**Still stuck?** See **[REPORTING_ISSUES.md](REPORTING_ISSUES.md)** for how to file a bug report that includes everything needed to diagnose it (diagnostics download + debug logs) in one pass.

*For detailed parameter reference, see the [Loxwiki Luxtronik Java Web Interface](https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1533935933/Java+Webinterface) or the [Bouni/python-luxtronik](https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/parameters.py) repository.*
