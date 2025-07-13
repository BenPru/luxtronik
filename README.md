# Luxtronik

If you like 🩷 this project, [sponsor it (click)](https://github.com/sponsors/BenPru).

## Warning

> :warning: **New Code-Base - PLEASE READ!** :warning:  
* Backup your data before update (different config structure!). If you make a downgrade of this integration (<2023.9) restore your data backup (The entries for Luxtronik in ./storage/core.config_entries + core.device_registry + core.entity_registry should be enough.)! If not you get double entities!
* This release has no more language selection. The HA backend language is used.
* Some entities which can not detected automaticly are hidden or disabled by default. In the devices you can find them and activate it. Please check this list before creating issues with entity whiches.
* The RBE Room Temperature Sensor is currently not implemented.
* The update sensor "rings" for new firmware versions, but the "Install"-Button has no function. The Firmware has to be installed manually. An the Install-Button is necessary to get notified.
* In the integration configuration you can set a ha sensor id for the indoor temperature value.

> :warning: **Known Issues** :warning:  
* Runtime warning "untimeWarning: coroutine ... was never awaited ...". [#116](https://github.com/BenPru/luxtronik/issues/116) [#138](https://github.com/BenPru/luxtronik/issues/138) [#108](https://github.com/BenPru/luxtronik/issues/108) Please don't create tickets for this!
* Cooling is not full implemented! [#128]([url](https://github.com/BenPru/luxtronik/issues/128))

This component has been created to be used with Home Assistant.

> :warning: **Use at your own risk!** :warning:  
> You can write config parameters to your heatpump, altering it's efficiency and functionality.  
> Please be careful.

Based on [Bouni/luxtronik](https://github.com/Bouni/luxtronik) / [Bouni/python-luxtronik](https://github.com/Bouni/python-luxtronik). ❤️

This component extends the original luxtronik component with automatic discovery of the heatpump und home assistant climate thermostat. The `Luxtronik` integration lets you monitor and control heat pump units containing a Luxtronik controller. It is used by various manufacturers such as:

- Alpha Innotec
- Siemens Novelan
- Roth
- Elco
- Buderus
- Nibe
- Wolf Heiztechnik

This integration works locally. It's only necessary to connect the Luxtronik controller to your network using an ethernet cable. No additional hard- or software is needed.

1. [Installation](#1-installation)  
1.1 [HACS (Recommended)](#11-hacs-recommended)  
1.2 [Manual installation](#12-manual-installation)  
2. [Adding Luxtronik](#2-adding-luxtronik)  
3. [Tips for using Luxtronik](#3-tips-for-using-luxtronik)  
3.1 [Energy use](#31-energy-use)  
3.2 [Additional sensors (advanced)](#32-additional-sensors-advanced)
4. [Support / Creating tickets](#4-support-tickets)

## 1. Installation

### 1.1 HACS (recommended)

Add the custom repo to HACS

1. Go to 'HACS > Integration'
2. Select 'Custom repositories' from the top right menu
3. Under Repository, enter '<https://github.com/BenPru/luxtronik>'
4. Under Category, select 'Integration'
5. Click 'Add'
The new integration will appear as a new integration and under 'Explore & Download Repositories' in the bottom right

Install the integration

1. Click on the new integration or find it under 'Explore & Download Repositories' in the bottom right with the search word 'luxtronik'.
  * Choose the one with the blue download button: ![image](https://github.com/BenPru/luxtronik/assets/32298537/84a7e17f-1ae2-471b-8f79-ca9cdab1d249)
2. Select 'download' at the bottom right.
3. Restart Home Assistant

### 1.2 Manual installation

Add the integration to Home Assistant

1. Download the latest release of the Luxtronik integration from this repository
2. In Home Assistant, create a folder 'config/custom_components'
3. Add the Luxtronik integration to the 'custom_components' folder;
4. Restart Home Assistant;

Install the integration

1. Add the Luxtronik integration to Home Assistant (`Settings -> Devices & services -> Add integration`);
2. Restart Home Assistant;

## 2. Adding Luxtronik

#### Autodiscovery

Your heatpump should be autodiscovered by home assistant.  
<img src="https://user-images.githubusercontent.com/5879533/178813978-bd8f13ff-ed27-4fa8-bfd0-6ff86a6e9786.png" width="300" />

Press `Configure` and follow the steps to the end.

#### Manual

'If auto discovery does not work, please give feedback with the first six chars of your luxtronik heatpump mac address, the original hostname, the manufacturer and model.

To add the heatpump manually go to `Settings -> Devices & services -> Add integration` and add a new Luxtronik device.'

Select Configure and review the settings.  
<img src="https://user-images.githubusercontent.com/32298537/267698990-e317633e-e78a-4341-92fb-a7022214ec1b.png" width="500" />

> ℹ️ Ensure the IP address is static. This can be configured in your router.'

## 3. Tips for using Luxtronik

It's not always clear from the name alone what an entity exactly means and how it effects your heatpump. The main source of information is ofcourse the [Luxtronik Operating Manual](https://mw.ait-group.net/files/docs/EN/A0220/83055400.pdf).

Another great source is [FHEM - Luxtronik 2.0](https://wiki.fhem.de/wiki/Luxtronik_2.0). It's in German so use Google Translate.  
It contains details about the various parameters and how to use them to optimize your heatpump efficiency. Read carfully though. Make small incremental changes and monitor your progress in Home Assistant. You don't want to miss out on this information.

### 3.1 Energy use

Not all heatpumps have build in electrical energy metering and instead only show the energy produced in heat, not the energy consumed in electricity. Adding a (strong) energy meter is a nice addition to measure the SCOP of your device. Shelly energy meters are recommended since they offer offer a [16A power plug](https://www.shelly.com/en-nl/products/product-overview/1xplug) and a [variety of in-line or clamp energy meters](https://www.shelly.com/en-nl/products/energy-metering-energy-efficiency) with various protection mechanisms.

### 3.2 Additional sensors (advanced)

If you miss a sensor please have a look in the devices under "+n entities not shown". Not all entities can autodetect by the integration. You can enable the entities by your self.

The most usefull sensors and parameters are created automaticly. But if you miss a sensor you can add it manually via yaml configuration like the original module from [Bouni/luxtronik](https://github.com/Bouni/luxtronik).

A short description of many of the available sensors can be found here [Loxwiki - Luxtronik Java Web Interface](https://loxwiki.atlassian.net/wiki/spaces/LOX/pages/1533935933/Java+Webinterface)

#### Parameter IDs

Take these files as a reference to figure ot which IDs to use:

- <https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/parameters.py>
- <https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/calculations.py>
- <https://github.com/Bouni/python-luxtronik/blob/master/luxtronik/visibilities.py>

#### Service

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

> ℹ️ Before changing a parameter it smart to first read the current value and note it somewhere in case you want to set it back to its original value.
All parameters can be configured as sensors and read that way.


### 4 Support Tickets
If you create a ticket please provide always a diagnostic file as issue attachment:
![image](https://github.com/BenPru/luxtronik/assets/32298537/89c26414-0304-438f-9204-79cf0a338db3)


## Some Screenshots

![image](https://user-images.githubusercontent.com/32298537/178588098-09e960f0-f849-475c-9afa-cf4a78e5d76d.png)
![image](https://user-images.githubusercontent.com/32298537/178588218-56f914f0-1ec5-4851-84ff-1d53bf8d4c1d.png)
![image](https://user-images.githubusercontent.com/32298537/178588500-2ec97e7f-c542-492c-9db0-3fcb68e1fe5c.png)
![image](https://user-images.githubusercontent.com/32298537/178588584-3a1004ff-dc8f-47bf-9c32-1d9aae0a3aeb.png)
![image](https://user-images.githubusercontent.com/32298537/178588670-0af53cc6-086d-4545-b3d0-0208043c188f.png)
![image](https://user-images.githubusercontent.com/32298537/178588738-6588f1c8-1840-4961-a4f8-c956df5f600c.png)
