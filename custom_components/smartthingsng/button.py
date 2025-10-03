"""Support for SmartThings button entities."""
from __future__ import annotations

import logging
from typing import Any

from pysmartthings import Capability

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceBroker
from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

# Mapping of SmartThings capabilities to button configurations
CAPABILITY_TO_BUTTON = {
    # Scene execution buttons
    Capability.scene_control: {
        "commands": ["execute"],
        "name": "Execute Scene",
        "icon": "mdi:play",
        "device_class": None,
    },
    # Doorbell buttons
    Capability.button: {
        "commands": ["push"],
        "name": "Push Button", 
        "icon": "mdi:gesture-tap-button",
        "device_class": None,
    },
    # Momentary switches (act as buttons)
    Capability.momentary: {
        "commands": ["push"],
        "name": "Momentary Switch",
        "icon": "mdi:radiobox-marked",
        "device_class": None,
    },
    # Emergency buttons  
    Capability.panic_alarm: {
        "commands": ["panic"],
        "name": "Panic Button",
        "icon": "mdi:alarm-light",
        "device_class": None,
    },
    # Water leak detector test buttons
    Capability.water_sensor: {
        "commands": ["test"],
        "name": "Test Water Sensor", 
        "icon": "mdi:water-alert",
        "device_class": None,
    },
    # Smoke detector test buttons
    Capability.smoke_detector: {
        "commands": ["test"],
        "name": "Test Smoke Detector",
        "icon": "mdi:smoke-detector",
        "device_class": None,
    },
    # Carbon monoxide detector test buttons
    Capability.carbon_monoxide_detector: {
        "commands": ["test"],
        "name": "Test CO Detector",
        "icon": "mdi:molecule-co",
        "device_class": None,
    },
    # Chime/doorbell buttons
    Capability.chime: {
        "commands": ["chime"],
        "name": "Chime",
        "icon": "mdi:bell-ring",
        "device_class": None,
    },
    # TV/Media control buttons
    Capability.media_input_source: {
        "commands": ["showInputSource"],
        "name": "Show Input Source",
        "icon": "mdi:television-guide", 
        "device_class": None,
    },
    # Washer/Dryer control buttons
    Capability.washer_operating_state: {
        "commands": ["start", "pause", "stop"],
        "name": "Washer Control",
        "icon": "mdi:washing-machine",
        "device_class": None,
    },
    Capability.dryer_operating_state: {
        "commands": ["start", "pause", "stop"],
        "name": "Dryer Control", 
        "icon": "mdi:tumble-dryer",
        "device_class": None,
    },
    # Dishwasher control buttons
    Capability.dishwasher_operating_state: {
        "commands": ["start", "pause", "stop"],
        "name": "Dishwasher Control",
        "icon": "mdi:dishwasher",
        "device_class": None,
    },
    # Oven control buttons
    Capability.oven_operating_state: {
        "commands": ["start", "pause", "stop"],
        "name": "Oven Control",
        "icon": "mdi:stove", 
        "device_class": None,
    },
    # Robot vacuum control buttons
    Capability.robot_cleaner_cleaning_mode: {
        "commands": ["start", "pause", "stop", "homing"],
        "name": "Robot Cleaner Control",
        "icon": "mdi:robot-vacuum",
        "device_class": None,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add button entities for a SmartThings config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    buttons = []
    
    for device in broker.devices.values():
        for capability in device.capabilities:
            if capability in CAPABILITY_TO_BUTTON:
                button_config = CAPABILITY_TO_BUTTON[capability]
                
                # Create a button for each command in the capability
                for command in button_config["commands"]:
                    buttons.append(
                        SmartThingsButton(
                            device=device,
                            capability=capability, 
                            command=command,
                            name=f"{button_config['name']} - {command.title()}",
                            icon=button_config["icon"],
                            device_class=button_config["device_class"],
                        )
                    )

    if buttons:
        async_add_entities(buttons)
        _LOGGER.debug("Added %d SmartThings button entities", len(buttons))


def get_capabilities(capabilities: list[str]) -> list[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        capability for capability in CAPABILITY_TO_BUTTON if capability in capabilities
    ]
    return supported if supported else None


class SmartThingsButton(SmartThingsEntity, ButtonEntity):
    """Define a SmartThings button entity."""

    def __init__(
        self,
        device,
        capability: str,
        command: str,
        name: str,
        icon: str,
        device_class: str | None,
    ) -> None:
        """Initialize the button."""
        super().__init__(device)
        self._capability = capability
        self._command = command
        self._attr_name = f"{device.label} {name}"
        self._attr_unique_id = f"{device.device_id}_{capability}_{command}"
        self._attr_icon = icon
        self._attr_device_class = device_class

    async def async_press(self) -> None:
        """Press the button - send the command to SmartThings."""
        try:
            # Send the command to the device
            result = await self._device.command(
                component_id="main",
                capability=self._capability,
                command=self._command,
                args=[]
            )
            
            _LOGGER.info(
                "Button pressed: %s executed %s.%s - Result: %s",
                self._attr_name,
                self._capability,
                self._command,
                result
            )
            
        except Exception as ex:
            _LOGGER.error(
                "Failed to press button %s (%s.%s): %s",
                self._attr_name,
                self._capability, 
                self._command,
                ex
            )
            raise

    @property 
    def available(self) -> bool:
        """Return True if the button is available."""
        # Button is available if device is connected and capability is supported
        return (
            self._device.status.switch_state != "unavailable" 
            and self._capability in self._device.capabilities
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "capability": self._capability,
            "command": self._command,
            "device_type": self._device.type,
            "device_id": self._device.device_id,
        }