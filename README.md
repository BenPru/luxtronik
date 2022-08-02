# Luxtronik

This component has been created to be used with Home Assistant.

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

'If auto discovery does not work, please give feedback with the first six chars of your luxtronik heatpump mac address and/or hostname.'

Select Configure and review the settings 
![image](https://user-images.githubusercontent.com/5879533/178814105-1dfc9445-1591-417b-9162-0b9f341cd0b2.png)

'Tip: Ensure the IP address is static. This can be configured in your router.'

# Some Screenshots
![image](https://user-images.githubusercontent.com/32298537/178588098-09e960f0-f849-475c-9afa-cf4a78e5d76d.png)
![image](https://user-images.githubusercontent.com/32298537/178588218-56f914f0-1ec5-4851-84ff-1d53bf8d4c1d.png)
![image](https://user-images.githubusercontent.com/32298537/178588500-2ec97e7f-c542-492c-9db0-3fcb68e1fe5c.png)
![image](https://user-images.githubusercontent.com/32298537/178588584-3a1004ff-dc8f-47bf-9c32-1d9aae0a3aeb.png)
![image](https://user-images.githubusercontent.com/32298537/178588670-0af53cc6-086d-4545-b3d0-0208043c188f.png)
![image](https://user-images.githubusercontent.com/32298537/178588738-6588f1c8-1840-4961-a4f8-c956df5f600c.png)
