"""Support for number entities through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Attribute, Capability

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

# Map capabilities to their number configurations
CAPABILITY_TO_NUMBER = {
    Capability.audio_volume: {
        "attribute": Attribute.volume,
        "command": "setVolume",
        "name": "Volume",
        "icon": "mdi:volume-high",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": "%",
        "mode": NumberMode.SLIDER,
    },
    Capability.refrigeration_setpoint: {
        "attribute": Attribute.refrigeration_setpoint,
        "command": "setRefrigerationSetpoint",
        "name": "Temperature Setpoint",
        "icon": "mdi:thermometer",
        "min": -20,
        "max": 20,
        "step": 1,
        "unit": UnitOfTemperature.CELSIUS,
        "mode": NumberMode.BOX,
    },
    Capability.oven_setpoint: {
        "attribute": Attribute.oven_setpoint,
        "command": "setOvenSetpoint",
        "name": "Oven Setpoint",
        "icon": "mdi:stove",
        "min": 0,
        "max": 300,
        "step": 5,
        "unit": UnitOfTemperature.CELSIUS,
        "mode": NumberMode.BOX,
    },
    Capability.infrared_level: {
        "attribute": Attribute.infrared_level,
        "command": "setInfraredLevel",
        "name": "Infrared Level",
        "icon": "mdi:lightbulb-on",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": "%",
        "mode": NumberMode.SLIDER,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add number entities for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    numbers = []
    
    for device in broker.devices.values():
        device_capabilities_for_number = broker.get_assigned(device.device_id, "number")
        
        for capability in device_capabilities_for_number:
            if capability not in CAPABILITY_TO_NUMBER:
                continue
            
            config = CAPABILITY_TO_NUMBER[capability]
            numbers.append(
                SmartThingsNumber(
                    device,
                    capability,
                    config["attribute"],
                    config["command"],
                    config["name"],
                    config["icon"],
                    config["min"],
                    config["max"],
                    config["step"],
                    config.get("unit"),
                    config.get("mode", NumberMode.BOX),
                )
            )
    
    async_add_entities(numbers)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        capability
        for capability in CAPABILITY_TO_NUMBER
        if capability in capabilities
    ]
    return supported if supported else None


class SmartThingsNumber(SmartThingsEntity, NumberEntity):
    """Define a SmartThings Number entity."""

    def __init__(
        self,
        device,
        capability: str,
        attribute: str,
        command: str,
        name: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: str | None,
        mode: NumberMode,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(device)
        self._capability = capability
        self._attribute = attribute
        self._command = command
        self._attr_name = f"{device.label} {name}"
        self._attr_unique_id = f"{device.device_id}.{capability}.{attribute}"
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        # Convert to int if step is 1 (discrete values)
        if self._attr_native_step == 1:
            value = int(value)
        
        # Use the device command to set the value
        result = await self._device.command(
            "main",
            self._capability,
            self._command,
            [value]
        )
        
        if result:
            # Update the status optimistically
            self._device.status.update_attribute_value(self._attribute, value)
            self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = getattr(self._device.status, self._attribute, None)
        
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        
        return None
