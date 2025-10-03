"""Support for vacuum entities through the SmartThings cloud API."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (StateVacuumEntity,
                                             VacuumEntityFeature)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pysmartthings import Attribute, Capability

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map SmartThings robot cleaner capabilities to vacuum functionality
CAPABILITY_TO_VACUUM = {
    Capability.robot_cleaner_cleaning_mode: {
        "name": "Robot Vacuum",
        "features": [
            VacuumEntityFeature.START,
            VacuumEntityFeature.PAUSE,
            VacuumEntityFeature.STOP,
            VacuumEntityFeature.RETURN_HOME,
            VacuumEntityFeature.FAN_SPEED,
            VacuumEntityFeature.STATE,
            VacuumEntityFeature.BATTERY,
        ],
        "icon": "mdi:robot-vacuum",
        "device_class": None,
    },
    Capability.robot_cleaner_movement: {
        "name": "Robot Cleaner",
        "features": [
            VacuumEntityFeature.START,
            VacuumEntityFeature.PAUSE,
            VacuumEntityFeature.STOP,
            VacuumEntityFeature.RETURN_HOME,
            VacuumEntityFeature.STATE,
        ],
        "icon": "mdi:robot-vacuum",
        "device_class": None,
    },
}

# SmartThings robot cleaner state mappings
ST_STATE_MAP = {
    # Movement states
    "homing": "returning",
    "charging": "docked",
    "cleaning": "cleaning",
    "idle": "idle",
    "paused": "paused",
    # Cleaning mode states
    "auto": "cleaning",
    "spot": "cleaning",
    "edge": "cleaning",
    "single": "cleaning",
    "stop": "idle",
    "pause": "paused",
}

# Available fan speeds/cleaning modes
FAN_SPEED_MAP = {
    "auto": "Auto",
    "quiet": "Quiet",
    "standard": "Standard",
    "medium": "Medium",
    "high": "High",
    "turbo": "Turbo",
    "max": "Max",
    # Additional modes
    "eco": "Eco",
    "spot": "Spot Clean",
    "edge": "Edge Clean",
    "single": "Single Room",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add vacuum entities for a SmartThings config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    vacuum_devices = []

    for device in broker.devices.values():
        vacuum_capabilities = get_vacuum_capabilities(device.capabilities)
        if vacuum_capabilities:
            vacuum_devices.append(SmartThingsVacuum(device, vacuum_capabilities))

    async_add_entities(vacuum_devices)


def get_vacuum_capabilities(capabilities: list[str]) -> list[str] | None:
    """Return vacuum capabilities if device supports vacuum functions."""
    vacuum_capabilities = [cap for cap in capabilities if cap in CAPABILITY_TO_VACUUM]
    return vacuum_capabilities if vacuum_capabilities else None


class SmartThingsVacuum(SmartThingsEntity, StateVacuumEntity):
    """Define a SmartThings Vacuum entity."""

    def __init__(self, device, capabilities: list[str]) -> None:
        """Initialize the vacuum entity."""
        super().__init__(device)
        self._capabilities = capabilities

        # Determine primary capability for naming and features
        self._primary_capability = self._get_primary_capability()
        config = CAPABILITY_TO_VACUUM[self._primary_capability]

        self._attr_name = f"{device.label} {config['name']}"
        self._attr_icon = config["icon"]
        self._attr_supported_features = self._get_supported_features()

        # Set available fan speeds based on device capabilities
        self._attr_fan_speed_list = self._get_available_fan_speeds()

    def _get_primary_capability(self) -> str:
        """Get the primary capability for this vacuum."""
        # Prefer cleaning_mode over movement for richer features
        if Capability.robot_cleaner_cleaning_mode in self._capabilities:
            return Capability.robot_cleaner_cleaning_mode
        return Capability.robot_cleaner_movement

    def _get_supported_features(self) -> VacuumEntityFeature:
        """Determine supported features based on available capabilities."""
        features = VacuumEntityFeature(0)

        for capability in self._capabilities:
            if capability in CAPABILITY_TO_VACUUM:
                cap_features = CAPABILITY_TO_VACUUM[capability]["features"]
                for feature in cap_features:
                    features |= feature

        # Always add basic state tracking
        features |= VacuumEntityFeature.STATE

        return features

    def _get_available_fan_speeds(self) -> list[str]:
        """Get available fan speeds/cleaning modes for this vacuum."""
        speeds = []

        # Check if device supports turbo mode
        if Capability.robot_cleaner_turbo_mode in self._device.capabilities:
            speeds.extend(["quiet", "standard", "turbo"])
        else:
            speeds.extend(["quiet", "standard", "high"])

        # Check if device supports different cleaning modes
        if Capability.robot_cleaner_cleaning_mode in self._capabilities:
            speeds.extend(["auto", "spot", "edge"])

        return [FAN_SPEED_MAP.get(speed, speed.title()) for speed in speeds]

    @property
    def state(self) -> str | None:
        """Return the current state of the vacuum."""
        # Check movement state first
        if Capability.robot_cleaner_movement in self._device.capabilities:
            movement = getattr(
                self._device.status, Attribute.robot_cleaner_movement, None
            )
            if movement and movement in ST_STATE_MAP:
                return ST_STATE_MAP[movement]

        # Check cleaning mode state
        if Capability.robot_cleaner_cleaning_mode in self._device.capabilities:
            mode = getattr(
                self._device.status, Attribute.robot_cleaner_cleaning_mode, None
            )
            if mode and mode in ST_STATE_MAP:
                return ST_STATE_MAP[mode]

        return "idle"

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum."""
        if Capability.battery in self._device.capabilities:
            return getattr(self._device.status, Attribute.battery, None)
        return None

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        # Check turbo mode first
        if Capability.robot_cleaner_turbo_mode in self._device.capabilities:
            turbo = getattr(
                self._device.status, Attribute.robot_cleaner_turbo_mode, None
            )
            if turbo == "on":
                return "Turbo"

        # Check cleaning mode
        if Capability.robot_cleaner_cleaning_mode in self._device.capabilities:
            mode = getattr(
                self._device.status, Attribute.robot_cleaner_cleaning_mode, None
            )
            if mode and mode in FAN_SPEED_MAP:
                return FAN_SPEED_MAP[mode]

        return "Standard"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}

        # Add current cleaning mode
        if Capability.robot_cleaner_cleaning_mode in self._device.capabilities:
            mode = getattr(
                self._device.status, Attribute.robot_cleaner_cleaning_mode, None
            )
            attributes["cleaning_mode"] = mode

        # Add movement status
        if Capability.robot_cleaner_movement in self._device.capabilities:
            movement = getattr(
                self._device.status, Attribute.robot_cleaner_movement, None
            )
            attributes["movement_status"] = movement

        # Add turbo mode status
        if Capability.robot_cleaner_turbo_mode in self._device.capabilities:
            turbo = getattr(
                self._device.status, Attribute.robot_cleaner_turbo_mode, None
            )
            attributes["turbo_mode"] = turbo

        # Add device capabilities for debugging
        attributes["vacuum_capabilities"] = self._capabilities

        return attributes

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        try:
            if Capability.robot_cleaner_cleaning_mode in self._capabilities:
                # Use cleaning mode capability for start command
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_cleaning_mode,
                    "setRobotCleanerCleaningMode",
                    ["auto"],
                )
            elif Capability.robot_cleaner_movement in self._capabilities:
                # Use movement capability for start command
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_movement,
                    "setRobotCleanerMovement",
                    ["cleaning"],
                )
            else:
                _LOGGER.error(
                    "No suitable capability for start command on %s", self.entity_id
                )
                return

            if result:
                _LOGGER.debug("Successfully started vacuum %s", self.entity_id)
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to start vacuum %s", self.entity_id)

        except Exception as ex:
            _LOGGER.error("Error starting vacuum %s: %s", self.entity_id, ex)

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        try:
            if Capability.robot_cleaner_cleaning_mode in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_cleaning_mode,
                    "setRobotCleanerCleaningMode",
                    ["pause"],
                )
            elif Capability.robot_cleaner_movement in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_movement,
                    "setRobotCleanerMovement",
                    ["paused"],
                )
            else:
                _LOGGER.error(
                    "No suitable capability for pause command on %s", self.entity_id
                )
                return

            if result:
                _LOGGER.debug("Successfully paused vacuum %s", self.entity_id)
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to pause vacuum %s", self.entity_id)

        except Exception as ex:
            _LOGGER.error("Error pausing vacuum %s: %s", self.entity_id, ex)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task."""
        try:
            if Capability.robot_cleaner_cleaning_mode in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_cleaning_mode,
                    "setRobotCleanerCleaningMode",
                    ["stop"],
                )
            elif Capability.robot_cleaner_movement in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_movement,
                    "setRobotCleanerMovement",
                    ["idle"],
                )
            else:
                _LOGGER.error(
                    "No suitable capability for stop command on %s", self.entity_id
                )
                return

            if result:
                _LOGGER.debug("Successfully stopped vacuum %s", self.entity_id)
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to stop vacuum %s", self.entity_id)

        except Exception as ex:
            _LOGGER.error("Error stopping vacuum %s: %s", self.entity_id, ex)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        try:
            if Capability.robot_cleaner_cleaning_mode in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_cleaning_mode,
                    "setRobotCleanerCleaningMode",
                    ["homing"],
                )
            elif Capability.robot_cleaner_movement in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_movement,
                    "setRobotCleanerMovement",
                    ["homing"],
                )
            else:
                _LOGGER.error(
                    "No suitable capability for return to base command on %s",
                    self.entity_id,
                )
                return

            if result:
                _LOGGER.debug(
                    "Successfully sent return to base command to vacuum %s",
                    self.entity_id,
                )
                self.async_write_ha_state()
            else:
                _LOGGER.error(
                    "Failed to send return to base command to vacuum %s", self.entity_id
                )

        except Exception as ex:
            _LOGGER.error(
                "Error sending return to base command to vacuum %s: %s",
                self.entity_id,
                ex,
            )

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        try:
            # Convert display name back to internal mode
            internal_mode = None
            for mode, display in FAN_SPEED_MAP.items():
                if display == fan_speed:
                    internal_mode = mode
                    break

            if not internal_mode:
                _LOGGER.error(
                    "Unknown fan speed %s for vacuum %s", fan_speed, self.entity_id
                )
                return

            # Set turbo mode if requested
            if (
                internal_mode == "turbo"
                and Capability.robot_cleaner_turbo_mode in self._device.capabilities
            ):
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_turbo_mode,
                    "setRobotCleanerTurboMode",
                    ["on"],
                )
            elif Capability.robot_cleaner_turbo_mode in self._device.capabilities:
                # Turn off turbo for other modes
                await self._device.command(
                    "main",
                    Capability.robot_cleaner_turbo_mode,
                    "setRobotCleanerTurboMode",
                    ["off"],
                )

            # Set cleaning mode
            if Capability.robot_cleaner_cleaning_mode in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_cleaning_mode,
                    "setRobotCleanerCleaningMode",
                    [internal_mode],
                )
            else:
                result = True  # Turbo mode change was successful

            if result:
                _LOGGER.debug(
                    "Successfully set fan speed to %s on vacuum %s",
                    fan_speed,
                    self.entity_id,
                )
                self.async_write_ha_state()
            else:
                _LOGGER.error(
                    "Failed to set fan speed to %s on vacuum %s",
                    fan_speed,
                    self.entity_id,
                )

        except Exception as ex:
            _LOGGER.error(
                "Error setting fan speed on vacuum %s: %s", self.entity_id, ex
            )

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Start a spot cleaning task."""
        try:
            if Capability.robot_cleaner_cleaning_mode in self._capabilities:
                result = await self._device.command(
                    "main",
                    Capability.robot_cleaner_cleaning_mode,
                    "setRobotCleanerCleaningMode",
                    ["spot"],
                )

                if result:
                    _LOGGER.debug(
                        "Successfully started spot cleaning on vacuum %s",
                        self.entity_id,
                    )
                    self.async_write_ha_state()
                else:
                    _LOGGER.error(
                        "Failed to start spot cleaning on vacuum %s", self.entity_id
                    )
            else:
                _LOGGER.error(
                    "Spot cleaning not supported on vacuum %s", self.entity_id
                )

        except Exception as ex:
            _LOGGER.error(
                "Error starting spot cleaning on vacuum %s: %s", self.entity_id, ex
            )
