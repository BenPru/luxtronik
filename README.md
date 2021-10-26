# Luxtronik

This component has been created to be used with Home Assistant.

Based on [Bouni/luxtronik](https://github.com/Bouni/luxtronik). This component extends the original luxtronik component with automatic discovery of the heatpump und home assistant climate thermostat.

The `Luxtronik` integration lets you control heat pump units controlled by a Luxtronik controller. It is used by various manufacturers such as:

- Alpha Innotec
- Siemens Novelan
- Roth
- Elco
- Buderus
- Nibe
- Wolf Heiztechnik

Its only necessary to connect the Luxtronik controller to your network, no additional hard- or software is needed.

## Configuration
Your heatpump should autodiscovered by home assistant.
If not, please give feedback with the first six chars of your luxtronik heatpump mac address and/or hostname.
