"""Opt-in rated-power estimates, independent of measured energy registers."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import get_sensor_data, key_exists
from .const import DeviceKey, LuxCalculation as LC, LuxOperationMode
from .coordinator import LuxtronikCoordinator
from .model import LuxtronikCoordinatorData

CONF_ESTIMATED_ENERGY = "estimated_energy"
CONF_RATED_ELECTRICAL_POWER = "rated_electrical_power"
CONF_RATED_THERMAL_POWER = "rated_thermal_power"

COUNTERS = {
    "heating": LC.C0064_OPERATION_HOURS_HEATING,
    "dhw": LC.C0065_OPERATION_HOURS_DHW,
    "compressor1": LC.C0056_COMPRESSOR1_OPERATION_HOURS,
    "compressor2": LC.C0058_COMPRESSOR2_OPERATION_HOURS,
}


def positive_power(value: Any) -> float | None:
    """Accept only a finite, positive rating in kW."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if isfinite(number) and number > 0 else None


class EnergyEstimate:
    """Keep weighted counter deltas and their baselines in one snapshot.

    Never integrate wall time: a missed poll or a repeated snapshot cannot
    add energy twice. A decrease establishes a new baseline without reducing
    totals or assuming when a controller reset happened.
    """

    def __init__(self, electrical_kw: float, thermal_kw: float | None) -> None:
        self.electrical_kw = electrical_kw
        self.thermal_kw = thermal_kw
        self.baselines: dict[str, float] = {}
        self.electrical = dict.fromkeys(COUNTERS, 0.0)
        self.thermal: dict[str, float] = dict.fromkeys(("heating", "dhw"), 0.0)
        self.valid: set[str] = set()
        self.multiple_compressors = False

    def restore(self, saved: Mapping[str, Any]) -> None:
        """Restore totals and baselines together, even after ratings change."""
        self.multiple_compressors = bool(saved.get("multiple_compressors", False))
        for name in ("baselines", "electrical", "thermal"):
            target = getattr(self, name)
            for key, value in saved.get(name, {}).items():
                if (
                    key in COUNTERS
                    and isinstance(value, int | float)
                    and isfinite(value)
                    and value >= 0
                ):
                    target[key] = float(value)

    def snapshot(self) -> dict[str, Any]:
        """Copy state so asynchronous storage sees a consistent snapshot."""
        return {
            "baselines": self.baselines.copy(),
            "electrical": self.electrical.copy(),
            "thermal": self.thermal.copy(),
            "multiple_compressors": self.multiple_compressors,
        }

    def update(self, data: LuxtronikCoordinatorData) -> None:
        """Apply each valid lifetime runtime reading, in controller seconds."""
        self.valid = set()
        # Output activity is evidence even before the runtime counter advances.
        if key_exists(data, LC.C0045_COMPRESSOR2) and get_sensor_data(
            data, LC.C0045_COMPRESSOR2
        ) in (True, 1):
            self.multiple_compressors = True
        for key, register in COUNTERS.items():
            if not key_exists(data, register):
                continue
            value = get_sensor_data(data, register)
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            if not isfinite(value) or value < 0:
                continue
            self.valid.add(key)
            if key == "compressor2" and value > 0:
                self.multiple_compressors = True
            previous = self.baselines.get(key)
            self.baselines[key] = float(value)
            if previous is None or value < previous:
                continue
            hours = (value - previous) / 3600
            self.electrical[key] += hours * self.electrical_kw
            if key in self.thermal and self.thermal_kw is not None:
                self.thermal[key] += hours * self.thermal_kw


def estimated_power(
    data: LuxtronikCoordinatorData, *, require_second: bool = False
) -> tuple[float | None, str | None]:
    """Return active compressor count and effective mode, without guessing off."""
    active = 0
    for register in (LC.C0044_COMPRESSOR, LC.C0045_COMPRESSOR2):
        if not key_exists(data, register):
            if register == LC.C0044_COMPRESSOR or require_second:
                return None, None
            continue
        value = get_sensor_data(data, register)
        if value not in (True, False, 0, 1):
            return None, None
        active += int(bool(value))
    if not active:
        return 0, None
    mode = (
        get_sensor_data(data, LC.C0080_STATUS)
        if key_exists(data, LC.C0080_STATUS)
        else None
    )
    return active, mode


async def async_setup_estimates(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: LuxtronikCoordinator
) -> list[EstimatedSensor]:
    """Load one persistent accumulator shared by all estimated entities."""
    config = {**entry.data, **entry.options}
    electrical = positive_power(config.get(CONF_RATED_ELECTRICAL_POWER))
    if not config.get(CONF_ESTIMATED_ENERGY, False) or electrical is None:
        return []
    tracker = EnergyEstimate(
        electrical, positive_power(config.get(CONF_RATED_THERMAL_POWER))
    )
    store = Store[dict[str, Any]](
        hass, 1, f"luxtronik2.estimated_energy.{entry.entry_id}", atomic_writes=True
    )
    if saved := await store.async_load():
        tracker.restore(saved)

    @callback
    def update() -> None:
        if coordinator.last_update_success:
            tracker.update(coordinator.data)
            store.async_delay_save(tracker.snapshot, 5)

    update()
    # Establish the initial baseline durably before any entities expose totals.
    await store.async_save(tracker.snapshot())

    async def save() -> None:
        await store.async_save(tracker.snapshot())

    coordinator.estimated_energy_save = save
    entry.async_on_unload(coordinator.async_add_listener(update))
    entities = []
    for circuit in ("heating", "dhw", "total"):
        entities.append(EstimatedSensor(coordinator, entry, tracker, circuit, "power"))
        entities.append(EstimatedSensor(coordinator, entry, tracker, circuit, "energy"))
        if tracker.thermal_kw is not None:
            entities.append(
                EstimatedSensor(coordinator, entry, tracker, circuit, "thermal_energy")
            )
    return entities


class EstimatedSensor(CoordinatorEntity[LuxtronikCoordinator], SensorEntity):
    """An explicitly estimated quantity with its own stable entity identity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LuxtronikCoordinator,
        entry: ConfigEntry,
        tracker: EnergyEstimate,
        circuit: str,
        quantity: str,
    ) -> None:
        super().__init__(coordinator)
        self.tracker = tracker
        self.circuit = circuit
        self.quantity = quantity
        key = f"estimated_{circuit}_{quantity}"
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_device_info = coordinator.get_device(DeviceKey.heatpump)
        self.entity_description = SensorEntityDescription(
            key=key,
            translation_key=key,
            device_class=(
                SensorDeviceClass.POWER
                if quantity == "power"
                else SensorDeviceClass.ENERGY
            ),
            state_class=(
                SensorStateClass.MEASUREMENT
                if quantity == "power"
                else SensorStateClass.TOTAL_INCREASING
            ),
            native_unit_of_measurement=(
                UnitOfPower.WATT if quantity == "power" else UnitOfEnergy.KILO_WATT_HOUR
            ),
            suggested_display_precision=0 if quantity == "power" else 3,
        )
        self._attr_extra_state_attributes = {
            "estimated": True,
            "rated_electrical_power_kw": tracker.electrical_kw,
        }
        if tracker.thermal_kw is not None:
            self._attr_extra_state_attributes["rated_thermal_power_kw"] = (
                tracker.thermal_kw
            )

    @property
    def native_value(self) -> float | None:
        """Read derived values without advancing any counter."""
        if self.quantity == "power":
            active, mode = estimated_power(
                self.coordinator.data, require_second=self.tracker.multiple_compressors
            )
            if active is None:
                return None
            if active == 0:
                return 0
            if self.circuit == "total":
                return active * self.tracker.electrical_kw * 1000
            if mode not in LuxOperationMode:
                return None
            expected = (
                LuxOperationMode.heating
                if self.circuit == "heating"
                else LuxOperationMode.domestic_water
            )
            return active * self.tracker.electrical_kw * 1000 if mode == expected else 0

        thermal = self.quantity == "thermal_energy"
        # The mode counters measure machine time, not individual compressor
        # time. Once a second compressor has run, no reliable electrical
        # heating/DHW split can be reconstructed from these registers.
        if (
            not thermal
            and self.circuit != "total"
            and self.tracker.multiple_compressors
        ):
            return None
        keys = (
            (("heating", "dhw") if thermal else ("compressor1", "compressor2"))
            if self.circuit == "total"
            else (self.circuit,)
        )
        required = set(keys)
        if (
            self.circuit == "total"
            and not thermal
            and not self.tracker.multiple_compressors
            and not key_exists(self.coordinator.data, COUNTERS["compressor2"])
        ):
            required.discard("compressor2")
        if not required.issubset(self.tracker.valid):
            return None
        values = self.tracker.thermal if thermal else self.tracker.electrical
        return sum(values[key] for key in keys)

    @property
    def available(self) -> bool:
        """Never expose stale power or incomplete energy as a fresh reading."""
        return super().available and self.native_value is not None
