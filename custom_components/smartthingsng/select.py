"""Support for select entities through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Attribute, Capability

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

# Map capabilities to their select configurations
CAPABILITY_TO_SELECT = {
    Capability.washer_mode: {
        "attribute": Attribute.washer_mode,
        "command": "setMachineState",
        "name": "Washer Mode",
        "icon": "mdi:washing-machine",
    },
    Capability.dryer_mode: {
        "attribute": Attribute.dryer_mode,
        "command": "setMachineState",
        "name": "Dryer Mode",
        "icon": "mdi:tumble-dryer",
    },
    Capability.air_conditioner_mode: {
        "attribute": Attribute.air_conditioner_mode,
        "command": "setAirConditionerMode",
        "name": "Air Conditioner Mode",
        "icon": "mdi:air-conditioner",
    },
    Capability.dishwasher_mode: {
        "attribute": Attribute.dishwasher_mode,
        "command": "setMachineState",
        "name": "Dishwasher Mode",
        "icon": "mdi:dishwasher",
    },
    Capability.oven_mode: {
        "attribute": Attribute.oven_mode,
        "command": "setOvenMode",
        "name": "Oven Mode",
        "icon": "mdi:stove",
    },
    Capability.robot_cleaner_cleaning_mode: {
        "attribute": Attribute.robot_cleaner_cleaning_mode,
        "command": "setRobotCleanerCleaningMode",
        "name": "Cleaning Mode",
        "icon": "mdi:robot-vacuum",
    },
    Capability.media_input_source: {
        "attribute": Attribute.input_source,
        "command": "setInputSource",
        "name": "Input Source",
        "icon": "mdi:video-input-hdmi",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add select entities for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    selects = []
    
    for device in broker.devices.values():
        device_capabilities_for_select = broker.get_assigned(device.device_id, "select")
        
        for capability in device_capabilities_for_select:
            if capability not in CAPABILITY_TO_SELECT:
                continue
            
            config = CAPABILITY_TO_SELECT[capability]
            selects.append(
                SmartThingsSelect(
                    device,
                    capability,
                    config["attribute"],
                    config["command"],
                    config["name"],
                    config["icon"],
                )
            )
    
    async_add_entities(selects)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        capability
        for capability in CAPABILITY_TO_SELECT
        if capability in capabilities
    ]
    return supported if supported else None


class SmartThingsSelect(SmartThingsEntity, SelectEntity):
    """Define a SmartThings Select entity."""

    def __init__(
        self,
        device,
        capability: str,
        attribute: str,
        command: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(device)
        self._capability = capability
        self._attribute = attribute
        self._command = command
        self._attr_name = f"{device.label} {name}"
        self._attr_unique_id = f"{device.device_id}.{capability}.{attribute}"
        self._attr_icon = icon

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Use the device command to set the mode/option
        result = await self._device.command(
            "main",
            self._capability,
            self._command,
            [option]
        )
        
        if result:
            # Update the status optimistically
            self._device.status.update_attribute_value(self._attribute, option)
            self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return getattr(self._device.status, self._attribute, None)

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        # Get supported modes from device status
        supported_attr = f"supported_{self._attribute}s"
        
        # Try to get supported options from device
        supported = getattr(self._device.status, supported_attr, None)
        
        if supported and isinstance(supported, list):
            return supported
        
        # Fallback to getting from attributes if available
        attr_obj = self._device.status.attributes.get(self._attribute)
        if attr_obj and hasattr(attr_obj, "values") and attr_obj.values:
            return list(attr_obj.values)
        
        # Last resort - return current value as single option
        current = self.current_option
        return [current] if current else []
