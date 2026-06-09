"""Predefined Select entity descriptions for Luxtronik."""

from __future__ import annotations

from homeassistant.const import EntityCategory

from .const import (
    DAY_SELECTOR_OPTIONS,
    DeviceKey,
    LuxDaySelectorParameter,
    LuxHeatingControlModeTypes,
    LuxMode,
    LuxParameter,
    LuxPoolPVMode,
    SensorKey as SK,
)
from .model import LuxtronikSelectEntityDescription

# ---- Options (always strings!) ------------------------------------
mode_options: list[str] = [
    m.value
    for m in (
        LuxMode.off,
        LuxMode.automatic,
        LuxMode.second_heatsource,
        LuxMode.party,
        LuxMode.holidays,
    )
]

mode_mk_options: list[str] = [
    m.value
    for m in (
        LuxMode.off,
        LuxMode.automatic,
        LuxMode.party,
        LuxMode.holidays,
    )
]

mode_pv_pool_options: list[str] = [
    m.value
    for m in (
        LuxPoolPVMode.automatic,
        LuxPoolPVMode.pv_off,
        LuxPoolPVMode.pool_party,
        LuxPoolPVMode.pool_holidays,
        LuxPoolPVMode.pool_off,
    )
]

heating_control_mode_options: list[str] = [m.value for m in LuxHeatingControlModeTypes]


# ---- Descriptions directly in SELECT_ENTITIES ---------------------
SELECT_ENTITIES: list[LuxtronikSelectEntityDescription] = [
    LuxtronikSelectEntityDescription(
        key=SK.THERMAL_DESINFECTION_DAY,
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LuxDaySelectorParameter.MONDAY,  # pyright: ignore[reportArgumentType]
        entity_category=EntityCategory.CONFIG,
        options=DAY_SELECTOR_OPTIONS,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.DOMESTIC_WATER_MODE_SELECTOR,
        device_key=DeviceKey.domestic_water,
        luxtronik_key=LuxParameter.P0004_MODE_DHW,
        options=mode_options,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.HEATING_MODE_SELECTOR,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0003_MODE_HEATING,
        options=mode_options,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.HEATING_MODE_MK1,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0695_MODE_HZ_MK1,
        entity_registry_enabled_default=False,
        options=mode_mk_options,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.HEATING_MODE_MK2,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0696_MODE_HZ_MK2,
        entity_registry_enabled_default=False,
        options=mode_mk_options,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.HEATING_MODE_MK3,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0779_MODE_HZ_MK3,
        entity_registry_enabled_default=False,
        options=mode_mk_options,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.HEATING_CONTROL_CIRCUIT_MODE,
        device_key=DeviceKey.heating,
        luxtronik_key=LuxParameter.P0103_HEATING_CONTROL_CIRCUIT_MODE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=heating_control_mode_options,
    ),
    LuxtronikSelectEntityDescription(
        key=SK.PV_MODE_SELECTOR,
        device_key=DeviceKey.heatpump,
        luxtronik_key=LuxParameter.P0119_MODE_PV,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=mode_pv_pool_options,
    ),
]
