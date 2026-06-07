# Luxtronik Home Assistant Integration

This is a Home Assistant integration for [Luxtronik heat pumps](https://www.alpha-innotec.com/en/products/accessories/control/luxtronik).

It is based on [Bouni/luxtronik](https://github.com/Bouni/luxtronik) which provides the groundwork for this integration. This integration extends the Bouni integration with with predefined entities and a full UI setup. Bouni en BenPru can run side by side.

If you like this project, give it a ⭐, or sponsor the developers:
* Project creator: [BenPru](https://github.com/sponsors/BenPru).
* Current developer: [rhammen](https://github.com/sponsors/rhammen).

It takes a lot of time and effort to keep up with changes (Home Assistant and Luxtronik Firmware). BenPru has handed over the project to the community fos us to maintain. This means the project depends on you to submit issues and work with the community's developers to improve the integration. 

Big thanks to [all community members](https://github.com/BenPru/luxtronik/graphs/contributors) who have contributed to this project. 

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

Click the button below to automatically add the custom repository to HACS:

[![Open your Home Assistant instance and show the add HACS repository dialog with a specific repository pre-filled.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BenPru&repository=Luxtronik&category=integration)

*(Alternatively: Open HACS, go to Integrations, click the three dots in the top right, select "Custom repositories", enter `https://github.com/BenPru/luxtronik`, and select "Integration" as the category).*

### Step 2: Install the Integration

1. Open HACS in Home Assistant.
2. In Home Assistant, go to **Integrations** -> **Explore & Download Repositories**.
3. Search for **Luxtronik**. Check that it's the BenPru integration by clicking on it. 
4. Click on the integration, then click **Download** at the bottom right.
5. **Restart** Home Assistant to load the new integration files.

### Step 3: Add the Luxtronik Device(s)

1. **Auto-discovery:** Home Assistant should automatically discover your heat pump. Check the **Settings -> Devices & Services** page and click **Configure**.
2. **Manual Addition:** If auto-discovery fails, click **Add Integration** in the bottom right corner, search for **Luxtronik**, and enter the IP address of your heat pump manually. *(Tip: Ensure the heat pump has a static IP in your router).*

---

## 2 Using Luxtronik

Entities and actions are organized into four logical devices in Home Assistant to keep things structured. Here is an overview of what each device does and how to use the most common entities.

### 2.1 Heatpump
This device represents the physical heat pump unit. It contains sensors and diagnostic entities such as electrical power consumption, thermal power output, operating hours, and current status.

**Most important entities:**
- **Status:** Shows whether the heat pump is heating, cooling, making hot water, or idle.
- **Power Consumption Sensors:** Ideal for tracking energy usage if your model supports it.
- **Errors/Lockouts:** Alerts if your heat pump is in an error state.

### 2.2 Heating
This device controls the space heating functionality (e.g., underfloor heating or radiators).

**Most important entities & actions:**
- **Heating Climate Entity (`climate.heating`):** The primary thermostat to view the current operation mode and adjust the target temperature.
- **Heating Operation Mode:** Choose between Automatic, Second Heatsource, Party (boost), Holidays (reduced), or Off.
- **Target Temperature Correction:** Quickly bump the heating target up or down by a few degrees without altering the main heating curve.

### 2.3 Cooling
If your heat pump supports active or passive cooling, this device manages it.

Basic entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Cooling** | Climate | &deg;C | The climate entity combines several of the entities below into a combined climate entity. It shows the current temperature and controls the *Cooling Mode* and *Cooling Target Temperature* (in case no thermostat is present) or *Room Thermostat Target* (in case a thermostat is present). Note: Cooling does not aim for the target temperature in the same way heating does. |
| **Cooling** | Select / Switch | on/off | Controls the state. "Off" disables cooling, while "On" allows cooling depending on the *Approval*, *Minimal Outdoor Temperture* and *Room Thermostat Target Temperature* entities. |
| **Cooling Target Temperature** | Number | &deg;C | The target water temperature sent into the house. This value is ignored if cooling is based on outdoor temperature. |
| **Approval** | Binary Sensor | - | Indicates if cooling is unlocked by the heat pump based on various factors such as outdoor temperature and room temperature. Consult the manual for more details |

Advanced entities:
| Name | Entity Type | Units | Description |
| :--- | :--- | :--- | :--- |
| **Cooling Minimal Flow Temperature** | Number | &deg;C | The minimal water temperature used for activating cooling. Default 18&deg;C. |
| **Minimal Outdoor Temperature** | Number | &deg;C | The minimal outdoor temperature which needs to be exceeded for a) the duration of the *start delay* or b) by 5&deg;C. |
| **Start Delay** | Number | h | Duration the minimal outdoor temperature must be exceeded before cooling starts. |
| **Stop Delay** | Number | h | Duration the minimal outdoor temperature must no longer be met before cooling stops. |

> **⚠️ Important:** If the cooling target temperature is set too low, condensation can form on floor tiles, pipes, and inside the heat pump. A brine heat pump should generally not use a target temperature below 18°C to avoid damage. Consult your manual for details.

> **ℹ️ Note:** The Energy input may not work as expected. This is a limitation of the Luxtronik firmware.

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

The amount of cooling can be controlled with *Cooling Target Temperature* when the heatpump is configured to cool based on fixed temperature ([page 17](https://mw.ait-group.net/files/docs/EN/A0220/83055400.pdf)).

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
| **Thermal Desinfection Day** | Select | Day | The day on which the thermal disinfection cycle is performed. |

> **ℹ️ Note:** It is not possible to trigger a thermal disinfection cycle on demand. It can be emulated by raising the *DHW Target Temperature*. 

#### 3.1.2 Automating DHW
Automations for DHW typically use the water heater entity or the Party/Boost mode. Common scenarios include pre-heating before showers, using excess solar energy to heat the tank, or scheduling anti‑legionella cycles.

<details>
<summary>⚙️ Example: Preheat DHW using solar power</summary>
```yaml
description: "Boost DHW when solar production is high"
trigger:
  - platform: numeric_state
    entity_id: sensor.solar_power
    above: 200
    for: "00:10:00"
    id: "solar_high"
action:
  - if:
      - condition: trigger
        id: "solar_high"
    then:
      - action: water_heater.set_temperature
        target:
          entity_id: water_heater.luxtronik_dhw
        data:
          temperature: 60
    else:
      - action: water_heater.set_temperature
        target:
          entity_id: water_heater.luxtronik_dhw
        data:
          temperature: 55
```
</details>

The amount of DHW heating can be controlled by the target temperature or by triggering the Party/Boost mode when a quick reheat is required.

---

## 3. Automations & Advanced Usage

### 3.1 Common Automations

Here are a few practical examples of how to automate your Luxtronik heat pump:

**1. Boost hot water before taking a bath:**
Trigger the "Party" mode on the DHW device when you need extra hot water quickly.


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

### 3.2 Advanced Entities (Configuration)

To protect your system from accidental misconfiguration, several advanced configuration parameters are **disabled by default**. They can be enabled manually from the Home Assistant entity registry if you need them.

**These advanced entities include:**
- **Thermal & Electrical Power Limits:** Used to throttle the heat pump's maximum power output.
- **Heating Curve Parameters:** (End temperature, Parallel shift, Night offset) These define how the heat pump reacts to outdoor temperatures. They are typically configured once during commissioning by your installer.
- **Heating Threshold Temperature:** The outdoor temperature above which the heating completely stops.
- **Second Heat Generator Settings:** Rules for when the backup electric heater is allowed to engage.

> **Tip:** Do not modify the heating curve or power limits frequently via automations. Heat pumps are slow-reacting systems and perform best when left running with stable parameters.

### 3.3 Energy Use

Not all heat pumps have built-in electrical energy metering. Some only show the thermal energy produced but not the electricity consumed. 
If you want to accurately measure the SCOP (Seasonal Coefficient of Performance) of your device, consider adding an external energy meter. Devices like Shelly offer a [16A power plug](https://www.shelly.com/en-nl/products/product-overview/1xplug) or [in-line/clamp energy meters](https://www.shelly.com/en-nl/products/energy-metering-energy-efficiency) that integrate perfectly with Home Assistant.

---

## 4. Troubleshooting

In case of connectivity or data issues, please perform the following steps first:
1. **Restart the heat pump.** Perform a full power cycle by turning off the physical switch, waiting a few moments, and turning it back on. This solves most Luxtronik controller network issues.
2. Ensure the heat pump has a **Static IP address** configured in your router.
3. Update to the **latest (beta) version** of this integration in HACS.
4. If issues persist, enable debug logging for this integration and check the Home Assistant logs.

*For detailed parameter reference, see the [Loxwiki Luxtronik Java Web Interface](https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1533935933/Java+Webinterface) or the [Bouni/python-luxtronik](https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/parameters.py) repository.*
