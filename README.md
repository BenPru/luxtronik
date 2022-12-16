# Luxtronik

This component has been created to be used with Home Assistant.

# ${{\color{red}Use\ it\ at\ your\ own\ risk!\ You\ can\ write\ config\ parameters\ to\ your\ heatpump.\ Please\ be\ careful.}}\$

Based on [Bouni/luxtronik](https://github.com/Bouni/luxtronik) / [Bouni/python-luxtronik](https://github.com/Bouni/python-luxtronik). This component extends the original luxtronik component with automatic discovery of the heatpump und home assistant climate thermostat.

The `Luxtronik` integration lets you monitor and control heat pump units containing a Luxtronik controller. It is used by various manufacturers such as:

- Alpha Innotec
- Siemens Novelan
- Roth
- Elco
- Buderus
- Nibe
- Wolf Heiztechnik

This integration works locally. It's only necessary to connect the Luxtronik controller to your network using an ethernet cable. No additional hard- or software is needed.

# Installation

1a. Install via HACS (recommended) 
1b. Install manually;
2 Configuration

## 1a. Install via HACS (recommended)

Add the custom repo to HACS
1. Go to 'HACS > Integration'
2. Select 'Custom repositories' from the top right menu
3. Under Repository, enter 'https://github.com/BenPru/luxtronik'
4. Under Category, select 'Integration'
5. Click 'Add'
The new integration will appear as a new integration and under 'Explore & Download Repositories' in the bottom right

Install the integration
1. Click on the new integration or find it under 'Explore & Download Repositories' in the bottom right
2. Select 'download' at the bottom right.
3. Restart Home Assistant

## 1b. Install manually

Add the integration to Home Assistant
1. Download the latest release of the Luxtronik integration from this repository
2. In Home Assistant, create a folder 'config/custom_components'
3. Add the Luxtronik integration to the 'custom_components' folder;
4. Restart Home Assistant;

Install the integration
1. Add the Luxtronik integration to Home Assistant ('menu: settings -> devices & services -> add integration');
2. Restart Home Assistant and clear the browser cache (optional).

## 2. Configuration
Your heatpump should be autodiscovered by home assistant.
![image](https://user-images.githubusercontent.com/5879533/178813978-bd8f13ff-ed27-4fa8-bfd0-6ff86a6e9786.png)

'If auto discovery does not work, please give feedback with the first six chars of your luxtronik heatpump mac address, the original hostname, the manufacturer and model. To add the heatpump manually go to Settings => Devices and Services => Add Integration and add a new luxtronik device.'

Select Configure and review the settings 
![image](https://user-images.githubusercontent.com/5879533/178814105-1dfc9445-1591-417b-9162-0b9f341cd0b2.png)

'Tip: Ensure the IP address is static. This can be configured in your router.'

## 2a. Additional sensors

The most usefull sensors and parameters are created automaticly. But if you miss a sensor you can add it manually via yaml configuration like the original module from [Bouni/luxtronik](https://github.com/Bouni/luxtronik).

### Parameter IDs

Take these files as a reference to figure ot which IDs to use:

- https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/parameters.py
- https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/calculations.py
- https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/visibilities.py

### Service

In order to change parameters on the Luxtronik conroller, you can use the following service:

```yaml
Domain: luxtronik2
Service: write
Service Data: {"parameter": "ID_Ba_Hz_akt", "value": "Automatic"}
```

- parameter
  - description: ID of the parameter.
  - type: string
- value
  - description: Value you want to set the parameter to.
  - type: [string, float]

Only a small number of the over 1100 parameters have a known funtion and only these can be written, these are:

- `ID_Ba_Hz_akt` The mode of operation of the heating circuit, possible values are "Automatic", "Second heatsource", "Party", "Holidays", "Off"
- `ID_Ba_Bw_akt` The mode of operation of the hot water circuit, possible valus are "Automatic", "Second heatsource", "Party", "Holidays", "Off"
- `ID_Soll_BWS_akt` The set point for hot water generation, for example 50.0 for 50.0°C 
- `ID_Einst_BA_Kuehl_akt` The mode of operation of the cooling circuit, possible values are "Automatic", "Off"
- `ID_Einst_KuehlFreig_akt` The outdoor temprature from wher on the cooling should start to operate, for example 24.0 
- `ID_Ba_Sw_akt` The mode of operation of the swimming pool heating circuit, possible values are "Automatic", "Party", "Holidays", "Off"
- `ID_Einst_TDC_Max_akt` Max. temperature difference of the hot water buffer tank, for example 70.0
- `ID_Sollwert_KuCft1_akt` Cooling set point for mixer circuit 1, for example 19.0
- `ID_Sollwert_KuCft2_akt` Cooling set point for mixer circuit 2, for example 19.0
- `ID_Sollwert_AtDif1_akt` Cooling working temperature difference 1, for example 5.0
- `ID_Sollwert_AtDif2_akt` Cooling working temperature difference 2, for example 5.0
- `ID_Ba_Hz_MK3_akt` The mode of operation of the heating mixer circuit 3, possible values are "Automatic", "Party", "Holidays", "Off"
- `ID_Einst_Kuhl_Zeit_Ein_akt` Cooling outdoor temperature overrun, for example 0.0
- `ID_Einst_Kuhl_Zeit_Aus_akt` Cooling outdoor temperature underrun, for example 0.0
- `ID_Einst_Solar_akt` Mode of operation for solar heat generation, "Automatic", "Second heatsource", "Party", "Holidays", "Off"
- `ID_Einst_BA_Lueftung_akt` Mode of operation of the integrated ventilation unit, posisble values are "Automatic", "Party", "Holidays", "Off"
- `ID_Sollwert_KuCft3_akt` Cooling set point for mixer circuit 3, for example 20.0
- `ID_Sollwert_AtDif3_akt` Cooling working temperature difference 3, for example 5.0

**Note:**

Before changing a parameter it smart to first read the current value and note it somewhere in case you want to set it back to its original value.
All parameters can be configured as sensors and read that way.

### Sensor

The Luxtronik sensor platform allows you to monitor the status values of a heat pump unit controlled by a Luxtronik controller.

Sensors are read-only. To write to the heatpump, use the provided service Luxtronik Integration - Service.

To use a Luxtronik sensor in your installation, add the following lines to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: luxtronik2
    sensors:
      - group: calculations
        id: ID_WEB_Temperatur_TVL
```

- group:
  - description: Value group where the ID is located, possible values are `calculations`, `parameters`, `visibilities`.
  - required: false, if group is provided in id.
  - type: string
- id:
  - description: The id of the value or the group.id (`calculations`, `parameters`, `visibilities`). e.g. calculations.ID_WEB_Temperatur_TVL
  - required: true
  - type: string
- friendly_name:
  - description: Sets a meaningful name for the sensor, if not provided the sensor will be named after the id, `sensor.luxtronik2_id_webemperatur_tvl` for example, otherwise `sensor.luxtronik2_temperature_forerun`.
  - required: false
  - type: string
- icon:
  - description: Set an icon for the sensor
  - required: false
  - type: string

## Full example

```yaml
# Example configuration.yaml entry
sensor:
  - platform: luxtronik2
    sensors:
      - group: calculations
        id: ID_WEB_Temperatur_TVL
      - id: calculations.ID_WEB_Temperatur_TVL
        friendly_name: Temperature forerun
        icon: mdi:thermometer
```

## Binary Sensor

The Luxtronik binary sensor platform allows you to monitor the status values of a heat pump unit controlled by a Luxtronik controller.

Binary sensors are read-only. To write to the heatpump, use the provided service Luxtronik Integration - Service.

To use a Luxtronik binary sensor in your installation, add the following lines to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
binary_sensor:
  - platform: luxtronik2
    sensors:
      - group: calculations
        id: ID_WEB_EVUin
```

- group:
  - description: Value group where the ID is located, possible values are `calculations`, `parameters`, `visibilities`.
  - required: false, if group is provided in id.
  - type: string
- id:
  - description: The id of the value or the group.id (`calculations`, `parameters`, `visibilities`). e.g. calculations.ID_WEB_Temperatur_TVL
  - required: true
  - type: string
- friendly_name:
  - description: Sets a meaningful name for the sensor, if not provided the sensor will be named after the id, `sensor.luxtronik2_id_web_evuin` for example, otherwise `sensor.luxtronik2_utility_company_lock`.
  - required: false
  - type: string
- icon:
  - description: Set an icon for the sensor
  - required: false
  - type: string
- invert:
  - description: Inverts the value
  - required: false
  - type: boolean
  - default: false

## Full example

```yaml
# Example configuration.yaml entry
binary_sensor:
  - platform: luxtronik2
    sensors:
      - group: calculations
        id: ID_WEB_EVUin
      - id: calculations.ID_WEB_EVUin
        friendly_name: Utility company lock
        icon: mdi:lock
```

# Some Screenshots
![image](https://user-images.githubusercontent.com/32298537/178588098-09e960f0-f849-475c-9afa-cf4a78e5d76d.png)
![image](https://user-images.githubusercontent.com/32298537/178588218-56f914f0-1ec5-4851-84ff-1d53bf8d4c1d.png)
![image](https://user-images.githubusercontent.com/32298537/178588500-2ec97e7f-c542-492c-9db0-3fcb68e1fe5c.png)
![image](https://user-images.githubusercontent.com/32298537/178588584-3a1004ff-dc8f-47bf-9c32-1d9aae0a3aeb.png)
![image](https://user-images.githubusercontent.com/32298537/178588670-0af53cc6-086d-4545-b3d0-0208043c188f.png)
![image](https://user-images.githubusercontent.com/32298537/178588738-6588f1c8-1840-4961-a4f8-c956df5f600c.png)
