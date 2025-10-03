"""Support for SmartThings media player entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (BrowseMedia,
                                                   MediaPlayerEntity,
                                                   MediaPlayerEntityFeature,
                                                   MediaPlayerState, MediaType)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pysmartthings import Capability

from . import DeviceBroker
from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

# Mapping of SmartThings capabilities to media player configurations
CAPABILITY_TO_MEDIA_PLAYER = {
    # Samsung TVs and Smart Displays
    Capability.tv_channel: {
        "name": "TV",
        "device_class": "tv",
        "features": [
            MediaPlayerEntityFeature.BROWSE_MEDIA,
            MediaPlayerEntityFeature.NEXT_TRACK,
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.PLAY,
            MediaPlayerEntityFeature.PREVIOUS_TRACK,
            MediaPlayerEntityFeature.SELECT_SOURCE,
            MediaPlayerEntityFeature.STOP,
            MediaPlayerEntityFeature.TURN_OFF,
            MediaPlayerEntityFeature.TURN_ON,
            MediaPlayerEntityFeature.VOLUME_MUTE,
            MediaPlayerEntityFeature.VOLUME_SET,
            MediaPlayerEntityFeature.VOLUME_STEP,
        ],
        "icon": "mdi:television",
    },
    # Audio devices and soundbars
    Capability.audio_volume: {
        "name": "Audio Device",
        "device_class": "speaker",
        "features": [
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.PLAY,
            MediaPlayerEntityFeature.STOP,
            MediaPlayerEntityFeature.VOLUME_MUTE,
            MediaPlayerEntityFeature.VOLUME_SET,
            MediaPlayerEntityFeature.VOLUME_STEP,
        ],
        "icon": "mdi:speaker",
    },
    # Media players with playback control
    Capability.media_playback: {
        "name": "Media Player",
        "device_class": "receiver",
        "features": [
            MediaPlayerEntityFeature.NEXT_TRACK,
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.PLAY,
            MediaPlayerEntityFeature.PREVIOUS_TRACK,
            MediaPlayerEntityFeature.STOP,
        ],
        "icon": "mdi:play-box",
    },
    # Input source control (TVs, receivers)
    Capability.media_input_source: {
        "name": "Media Input",
        "device_class": "receiver",
        "features": [
            MediaPlayerEntityFeature.SELECT_SOURCE,
        ],
        "icon": "mdi:video-input-hdmi",
    },
}

# SmartThings to HA state mapping
SMARTTHINGS_TO_HA_STATE = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.IDLE,
    "buffering": MediaPlayerState.PLAYING,  # Treat buffering as playing
    "idle": MediaPlayerState.IDLE,
    "off": MediaPlayerState.OFF,
    "on": MediaPlayerState.ON,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add media player entities for a SmartThings config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    media_players = []

    for device in broker.devices.values():
        capabilities = device.capabilities

        # Check for media player capabilities
        supported_capabilities = get_capabilities(capabilities)
        if supported_capabilities:
            # Create media player entity
            media_players.append(
                SmartThingsMediaPlayer(
                    device=device,
                    capabilities=supported_capabilities,
                )
            )

    if media_players:
        async_add_entities(media_players)
        _LOGGER.debug("Added %d SmartThings media player entities", len(media_players))


def get_capabilities(capabilities: list[str]) -> list[str] | None:
    """Return supported media player capabilities if any are present."""
    supported = [
        capability
        for capability in CAPABILITY_TO_MEDIA_PLAYER
        if capability in capabilities
    ]
    return supported if supported else None


class SmartThingsMediaPlayer(SmartThingsEntity, MediaPlayerEntity):
    """Define a SmartThings media player entity."""

    def __init__(self, device, capabilities: list[str]) -> None:
        """Initialize the media player."""
        super().__init__(device)
        self._capabilities = capabilities

        # Determine primary capability for naming and features
        if Capability.tv_channel in capabilities:
            self._primary_capability = Capability.tv_channel
            self._config = CAPABILITY_TO_MEDIA_PLAYER[Capability.tv_channel]
        elif Capability.audio_volume in capabilities:
            self._primary_capability = Capability.audio_volume
            self._config = CAPABILITY_TO_MEDIA_PLAYER[Capability.audio_volume]
        elif Capability.media_playback in capabilities:
            self._primary_capability = Capability.media_playback
            self._config = CAPABILITY_TO_MEDIA_PLAYER[Capability.media_playback]
        else:
            self._primary_capability = Capability.media_input_source
            self._config = CAPABILITY_TO_MEDIA_PLAYER[Capability.media_input_source]

        self._attr_name = f"{device.label} {self._config['name']}"
        self._attr_unique_id = f"{device.device_id}_media_player"
        self._attr_icon = self._config["icon"]
        self._attr_device_class = self._config["device_class"]

        # Combine features from all supported capabilities
        self._attr_supported_features = MediaPlayerEntityFeature(0)
        for capability in capabilities:
            if capability in CAPABILITY_TO_MEDIA_PLAYER:
                for feature in CAPABILITY_TO_MEDIA_PLAYER[capability]["features"]:
                    self._attr_supported_features |= feature

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the media player."""
        # Check various status attributes for state
        if (
            hasattr(self._device.status, "switch")
            and self._device.status.switch == "off"
        ):
            return MediaPlayerState.OFF

        # TV channel state
        if (
            hasattr(self._device.status, "tv_channel_name")
            and self._device.status.tv_channel_name
        ):
            return MediaPlayerState.ON

        # Media playback state
        if hasattr(self._device.status, "playback_status"):
            st_state = self._device.status.playback_status
            return SMARTTHINGS_TO_HA_STATE.get(st_state, MediaPlayerState.IDLE)

        # Audio volume indicates device is on
        if (
            hasattr(self._device.status, "volume")
            and self._device.status.volume is not None
        ):
            return MediaPlayerState.ON

        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (
            hasattr(self._device.status, "volume")
            and self._device.status.volume is not None
        ):
            return self._device.status.volume / 100.0
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if hasattr(self._device.status, "mute"):
            return self._device.status.mute == "muted"
        return None

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        if hasattr(self._device.status, "input_source"):
            return self._device.status.input_source
        elif hasattr(self._device.status, "tv_channel_name"):
            return self._device.status.tv_channel_name
        return None

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        if hasattr(self._device.status, "supported_input_sources"):
            return self._device.status.supported_input_sources
        # Common TV input sources as fallback
        return ["HDMI1", "HDMI2", "HDMI3", "HDMI4", "USB", "TV", "AV"]

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        if (
            hasattr(self._device.status, "tv_channel_name")
            and self._device.status.tv_channel_name
        ):
            return MediaType.CHANNEL
        return MediaType.MUSIC  # Default for audio devices

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if hasattr(self._device.status, "tv_channel_name"):
            return self._device.status.tv_channel_name
        elif hasattr(self._device.status, "media_title"):
            return self._device.status.media_title
        return None

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        if hasattr(self._device.status, "media_artist"):
            return self._device.status.media_artist
        return None

    @property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        if hasattr(self._device.status, "tv_channel"):
            return self._device.status.tv_channel
        return None

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        if Capability.switch in self._device.capabilities:
            await self._device.command("main", Capability.switch, "on")
        else:
            _LOGGER.warning("Device %s does not support power on", self._device.label)

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        if Capability.switch in self._device.capabilities:
            await self._device.command("main", Capability.switch, "off")
        else:
            _LOGGER.warning("Device %s does not support power off", self._device.label)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if Capability.audio_volume in self._capabilities:
            volume_percent = int(volume * 100)
            await self._device.command(
                "main", Capability.audio_volume, "setVolume", [volume_percent]
            )
        else:
            _LOGGER.warning(
                "Device %s does not support volume control", self._device.label
            )

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        if Capability.audio_volume in self._capabilities:
            await self._device.command("main", Capability.audio_volume, "volumeUp")
        else:
            _LOGGER.warning("Device %s does not support volume up", self._device.label)

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        if Capability.audio_volume in self._capabilities:
            await self._device.command("main", Capability.audio_volume, "volumeDown")
        else:
            _LOGGER.warning(
                "Device %s does not support volume down", self._device.label
            )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if Capability.audio_volume in self._capabilities:
            command = "mute" if mute else "unmute"
            await self._device.command("main", Capability.audio_volume, command)
        else:
            _LOGGER.warning("Device %s does not support mute", self._device.label)

    async def async_media_play(self) -> None:
        """Send play command."""
        if Capability.media_playback in self._capabilities:
            await self._device.command("main", Capability.media_playback, "play")
        else:
            _LOGGER.warning("Device %s does not support play", self._device.label)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        if Capability.media_playback in self._capabilities:
            await self._device.command("main", Capability.media_playback, "pause")
        else:
            _LOGGER.warning("Device %s does not support pause", self._device.label)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if Capability.media_playback in self._capabilities:
            await self._device.command("main", Capability.media_playback, "stop")
        else:
            _LOGGER.warning("Device %s does not support stop", self._device.label)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if Capability.media_playback in self._capabilities:
            await self._device.command("main", Capability.media_playback, "fastForward")
        elif Capability.tv_channel in self._capabilities:
            await self._device.command("main", Capability.tv_channel, "channelUp")
        else:
            _LOGGER.warning("Device %s does not support next track", self._device.label)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if Capability.media_playback in self._capabilities:
            await self._device.command("main", Capability.media_playback, "rewind")
        elif Capability.tv_channel in self._capabilities:
            await self._device.command("main", Capability.tv_channel, "channelDown")
        else:
            _LOGGER.warning(
                "Device %s does not support previous track", self._device.label
            )

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if Capability.media_input_source in self._capabilities:
            await self._device.command(
                "main", Capability.media_input_source, "setInputSource", [source]
            )
        elif Capability.tv_channel in self._capabilities:
            # Try to set channel by name or number
            if source.isdigit():
                await self._device.command(
                    "main", Capability.tv_channel, "setTvChannel", [source]
                )
            else:
                await self._device.command(
                    "main", Capability.tv_channel, "setTvChannelName", [source]
                )
        else:
            _LOGGER.warning(
                "Device %s does not support source selection", self._device.label
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "capabilities": self._capabilities,
            "primary_capability": self._primary_capability,
            "device_type": self._device.type,
            "device_id": self._device.device_id,
        }

        # Add relevant status attributes
        if hasattr(self._device.status, "tv_channel"):
            attributes["tv_channel"] = self._device.status.tv_channel
        if hasattr(self._device.status, "input_source"):
            attributes["input_source"] = self._device.status.input_source
        if hasattr(self._device.status, "supported_input_sources"):
            attributes["supported_input_sources"] = (
                self._device.status.supported_input_sources
            )
        if hasattr(self._device.status, "volume"):
            attributes["volume"] = self._device.status.volume
        if hasattr(self._device.status, "mute"):
            attributes["mute"] = self._device.status.mute
        if hasattr(self._device.status, "playback_status"):
            attributes["playback_status"] = self._device.status.playback_status

        return attributes

    @property
    def available(self) -> bool:
        """Return True if the media player is available."""
        # Media player is available if device is connected
        return self._device.status.switch_state != "unavailable" and any(
            cap in self._device.capabilities for cap in self._capabilities
        )
