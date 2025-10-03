"""Support for SmartThings Cloud."""

from __future__ import annotations

import asyncio
import importlib
import logging
from collections.abc import Iterable
from http import HTTPStatus

import voluptuous as vol
from aiohttp.client_exceptions import (ClientConnectionError,
                                       ClientResponseError)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (CONF_ACCESS_TOKEN, CONF_CLIENT_ID,
                                 CONF_CLIENT_SECRET)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from pysmartapp.event import EVENT_TYPE_DEVICE
from pysmartthings import Attribute, Capability, Device, SmartThings

# Import config_flow conditionally to avoid import issues in CI
try:
    from .config_flow import SmartThingsFlowHandler  # noqa: F401
except ImportError:
    # Skip config flow import when running outside Home Assistant
    SmartThingsFlowHandler = None
from .const import (CONF_APP_ID, CONF_INSTALLED_APP_ID, CONF_LOCATION_ID,
                    CONF_REFRESH_TOKEN, DATA_BROKERS, DATA_MANAGER, DOMAIN,
                    EVENT_BUTTON, PLATFORMS, SIGNAL_SMARTTHINGS_UPDATE,
                    TOKEN_REFRESH_INTERVAL)
# Import smartapp functions conditionally
try:
    from .smartapp import (format_unique_id, setup_smartapp,
                           setup_smartapp_endpoint, smartapp_sync_subscriptions,
                           unload_smartapp_endpoint, validate_installed_app,
                           validate_webhook_requirements)
except ImportError:
    # Create mock functions when running outside Home Assistant
    def format_unique_id(*args): return "mock_id"
    def setup_smartapp(*args): return None
    def setup_smartapp_endpoint(*args): return None
    def smartapp_sync_subscriptions(*args): return None
    def unload_smartapp_endpoint(*args): return None
    def validate_installed_app(*args): return True
    def validate_webhook_requirements(*args): return True

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the SmartThings platform."""
    await setup_smartapp_endpoint(hass, False)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle migration of a previous version config entry.

    A config entry created under a previous version must go through the
    integration setup again so we can properly retrieve the needed data
    elements. Force this by removing the entry and triggering a new flow.
    """
    # Remove the entry which will invoke the callback to delete the app.
    hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
    # only create new flow if there isn't a pending one for SmartThings.
    if not hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )

    # Return False because it could not be migrated.
    return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize config entry which represents an installed SmartApp."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=format_unique_id(
                entry.data[CONF_APP_ID], entry.data[CONF_LOCATION_ID]
            ),
        )

    if not validate_webhook_requirements(hass):
        _LOGGER.warning(
            "The 'base_url' of the 'http' integration must be configured and start with"
            " 'https://'"
        )
        return False

    # Create refresh token function for modern API
    async def refresh_token_func() -> str:
        """Get current access token from config entry."""
        return entry.data[CONF_ACCESS_TOKEN]

    api = SmartThings(
        session=async_get_clientsession(hass),
        refresh_token_function=refresh_token_func,
        request_timeout=10,
    )

    remove_entry = False
    try:
        # See if the app is already setup. This occurs when there are
        # installs in multiple SmartThings locations (valid use-case)
        manager = hass.data[DOMAIN][DATA_MANAGER]
        smart_app = manager.smartapps.get(entry.data[CONF_APP_ID])
        if not smart_app:
            # Validate and setup the app.
            app = await api.app(entry.data[CONF_APP_ID])
            smart_app = setup_smartapp(hass, app)

        # Validate and retrieve the installed app.
        installed_app = await validate_installed_app(
            api, entry.data[CONF_INSTALLED_APP_ID]
        )

        # Get scenes
        scenes = await async_get_entry_scenes(entry, api)

        # Get SmartApp token to sync subscriptions
        token = await api.generate_tokens(
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
            entry.data[CONF_REFRESH_TOKEN],
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: token.refresh_token}
        )

        # Get devices and their current status
        devices = await api.get_devices(location_ids=[installed_app.location_id])

        async def retrieve_device_status(device):
            try:
                await device.status.refresh()
            except ClientResponseError:
                _LOGGER.debug(
                    (
                        "Unable to update status for device: %s (%s), the device will"
                        " be excluded"
                    ),
                    device.label,
                    device.device_id,
                    exc_info=True,
                )
                devices.remove(device)

        await asyncio.gather(*(retrieve_device_status(d) for d in devices.copy()))

        # Sync device subscriptions
        await smartapp_sync_subscriptions(
            hass,
            token.access_token,
            installed_app.location_id,
            installed_app.installed_app_id,
            devices,
        )

        # Setup device broker
        broker = DeviceBroker(hass, entry, token, smart_app, devices, scenes)
        broker.connect()
        hass.data[DOMAIN][DATA_BROKERS][entry.entry_id] = broker

    except ClientResponseError as ex:
        if ex.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            _LOGGER.exception(
                (
                    "Unable to setup configuration entry '%s' - please reconfigure the"
                    " integration"
                ),
                entry.title,
            )
            remove_entry = True
        else:
            _LOGGER.debug(ex, exc_info=True)
            raise ConfigEntryNotReady from ex
    except (ClientConnectionError, RuntimeWarning) as ex:
        _LOGGER.debug(ex, exc_info=True)
        raise ConfigEntryNotReady from ex

    if remove_entry:
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        # only create new flow if there isn't a pending one for SmartThings.
        if not hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}
                )
            )
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services for this integration
    await async_register_services(hass)

    return True


async def async_get_entry_scenes(entry: ConfigEntry, api):
    """Get the scenes within an integration."""
    try:
        return await api.get_scenes(location_id=entry.data[CONF_LOCATION_ID])
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.FORBIDDEN:
            _LOGGER.exception(
                (
                    "Unable to load scenes for configuration entry '%s' because the"
                    " access token does not have the required access"
                ),
                entry.title,
            )
        else:
            raise
    return []


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS].pop(entry.entry_id, None)
    if broker:
        broker.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Perform clean-up when entry is being removed."""

    async def refresh_token_func() -> str:
        return entry.data[CONF_ACCESS_TOKEN]

    api = SmartThings(
        session=async_get_clientsession(hass),
        refresh_token_function=refresh_token_func,
        request_timeout=10,
    )

    # Remove the installed_app, which if already removed raises a HTTPStatus.FORBIDDEN error.
    installed_app_id = entry.data[CONF_INSTALLED_APP_ID]
    try:
        await api.delete_installed_app(installed_app_id)
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.FORBIDDEN:
            _LOGGER.debug(
                "Installed app %s has already been removed",
                installed_app_id,
                exc_info=True,
            )
        else:
            raise
    _LOGGER.debug("Removed installed app %s", installed_app_id)

    # Remove the app if not referenced by other entries, which if already
    # removed raises a HTTPStatus.FORBIDDEN error.
    all_entries = hass.config_entries.async_entries(DOMAIN)
    app_id = entry.data[CONF_APP_ID]
    app_count = sum(1 for entry in all_entries if entry.data[CONF_APP_ID] == app_id)
    if app_count > 1:
        _LOGGER.debug(
            (
                "App %s was not removed because it is in use by other configuration"
                " entries"
            ),
            app_id,
        )
        return
    # Remove the app
    try:
        await api.delete_app(app_id)
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.FORBIDDEN:
            _LOGGER.debug("App %s has already been removed", app_id, exc_info=True)
        else:
            raise
    _LOGGER.debug("Removed app %s", app_id)

    if len(all_entries) == 1:
        await unload_smartapp_endpoint(hass)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for SmartThings NG."""

    # Only register services once
    if hass.services.has_service(DOMAIN, "send_command"):
        return

    async def send_command_service(call):
        """Send a custom command to a SmartThings device."""
        device_id = call.data.get("device_id")
        component_id = call.data.get("component_id", "main")
        capability = call.data.get("capability")
        command = call.data.get("command")
        arguments = call.data.get("arguments", [])

        if not all([device_id, capability, command]):
            _LOGGER.error("send_command requires device_id, capability, and command")
            return

        # Get the first entry to access the API
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.error("No SmartThings integration configured")
            return

        entry = entries[0]  # Use the first entry

        try:
            # Create API instance
            async def refresh_token_func() -> str:
                return entry.data[CONF_ACCESS_TOKEN]

            api = SmartThings(
                session=async_get_clientsession(hass),
                refresh_token_function=refresh_token_func,
                request_timeout=10,
            )

            # Send the command
            await api.execute_device_command(
                device_id=device_id,
                capability=capability,
                command=command,
                component=component_id,
                argument=arguments,
            )
            _LOGGER.info(
                "Command sent to %s: %s.%s(%s)",
                device_id,
                capability,
                command,
                arguments,
            )
        except Exception as ex:
            _LOGGER.error(
                "Failed to send command to %s: %s.%s(%s) - Error: %s",
                device_id,
                capability,
                command,
                arguments,
                ex,
            )

    async def refresh_device_service(call):
        """Refresh a SmartThings device status."""
        device_id = call.data.get("device_id")

        if not device_id:
            _LOGGER.error("refresh_device requires device_id")
            return

        # Find the device in all brokers
        device = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            broker = hass.data[DOMAIN][DATA_BROKERS].get(entry.entry_id)
            if broker and device_id in broker.devices:
                device = broker.devices[device_id]
                break

        if not device:
            _LOGGER.error("Device %s not found", device_id)
            return

        try:
            await device.status.refresh()
            _LOGGER.info("Refreshed device %s status", device_id)

            # Trigger update for all entities of this device
            from homeassistant.helpers.dispatcher import async_dispatcher_send

            async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, {device_id})

        except Exception as ex:
            _LOGGER.error("Failed to refresh device %s: %s", device_id, ex)

    async def execute_scene_service(call):
        """Execute a SmartThings scene."""
        scene_id = call.data.get("scene_id")

        if not scene_id:
            _LOGGER.error("execute_scene requires scene_id")
            return

        # Get the first entry to access the API
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.error("No SmartThings integration configured")
            return

        entry = entries[0]  # Use the first entry

        try:
            # Create API instance
            async def refresh_token_func() -> str:
                return entry.data[CONF_ACCESS_TOKEN]

            api = SmartThings(
                session=async_get_clientsession(hass),
                refresh_token_function=refresh_token_func,
                request_timeout=10,
            )

            # Execute the scene
            await api.execute_scene(scene_id)
            _LOGGER.info("Executed scene %s", scene_id)
        except Exception as ex:
            _LOGGER.error("Failed to execute scene %s: %s", scene_id, ex)

    async def get_diagnostics_service(call):
        """Get comprehensive SmartThings integration diagnostics."""
        import time
        from datetime import datetime, timezone

        diagnostics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "integration_version": "1.7.0",
            "pysmartthings_version": getattr(SmartThings, "__version__", "unknown"),
            "home_assistant_version": hass.config.version,
            "entries": [],
        }

        for entry in hass.config_entries.async_entries(DOMAIN):
            broker = hass.data[DOMAIN][DATA_BROKERS].get(entry.entry_id)
            if not broker:
                continue

            entry_diag = {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "state": entry.state.value,
                "device_count": len(broker.devices),
                "scene_count": len(broker.scenes),
                "devices": [],
            }

            for device in broker.devices.values():
                device_diag = {
                    "device_id": device.device_id,
                    "label": device.label,
                    "type": device.type,
                    "manufacturer": device.status.ocf_manufacturer_name,
                    "model": device.status.ocf_model_number,
                    "firmware": device.status.ocf_firmware_version,
                    "hardware": device.status.ocf_hardware_version,
                    "capabilities": list(device.capabilities),
                    "components": (
                        list(device.components.keys()) if device.components else []
                    ),
                    "status_attributes": len(device.status.__dict__),
                    "last_update": getattr(device.status, "_last_update", None),
                }

                # Add health indicators
                try:
                    device_diag["health"] = {
                        "reachable": hasattr(device.status, "switch_state")
                        and device.status.switch_state != "unavailable",
                        "battery_level": getattr(device.status, "battery", None),
                        "signal_strength": getattr(device.status, "lqi", None)
                        or getattr(device.status, "rssi", None),
                    }
                except Exception as ex:
                    device_diag["health"] = {"error": str(ex)}

                entry_diag["devices"].append(device_diag)

            diagnostics["entries"].append(entry_diag)

        # Store diagnostics in hass data for retrieval
        if "diagnostics" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["diagnostics"] = {}
        hass.data[DOMAIN]["diagnostics"]["last_report"] = diagnostics

        _LOGGER.info(
            "Generated diagnostics report with %d entries, %d total devices",
            len(diagnostics["entries"]),
            sum(len(e["devices"]) for e in diagnostics["entries"]),
        )

        # Optionally create a persistent notification
        if call.data.get("create_notification", False):
            hass.components.persistent_notification.create(
                f"SmartThings NG Diagnostics Report Generated\n\n"
                f"Integration Version: {diagnostics['integration_version']}\n"
                f"Entries: {len(diagnostics['entries'])}\n"
                f"Total Devices: {sum(len(e['devices']) for e in diagnostics['entries'])}\n"
                f"Generated: {diagnostics['timestamp']}",
                title="SmartThings NG Diagnostics",
                notification_id="smartthingsng_diagnostics",
            )

    async def device_health_check_service(call):
        """Perform comprehensive health check on SmartThings devices."""
        import time
        from datetime import datetime, timezone

        device_id = call.data.get("device_id")
        check_all = call.data.get("check_all", False)

        if not device_id and not check_all:
            _LOGGER.error(
                "device_health_check requires either device_id or check_all=true"
            )
            return

        health_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks_performed": [],
        }

        devices_to_check = []

        # Collect devices to check
        for entry in hass.config_entries.async_entries(DOMAIN):
            broker = hass.data[DOMAIN][DATA_BROKERS].get(entry.entry_id)
            if not broker:
                continue

            if check_all:
                devices_to_check.extend(broker.devices.values())
            elif device_id and device_id in broker.devices:
                devices_to_check.append(broker.devices[device_id])
                break

        if not devices_to_check:
            _LOGGER.error("No devices found to check health")
            return

        for device in devices_to_check:
            start_time = time.time()
            health_check = {
                "device_id": device.device_id,
                "label": device.label,
                "checks": {},
                "overall_health": "unknown",
                "check_duration_ms": 0,
            }

            try:
                # Test basic connectivity
                original_status = dict(device.status.__dict__)
                await device.status.refresh()
                refresh_time = time.time() - start_time

                health_check["checks"]["connectivity"] = {
                    "status": "ok",
                    "response_time_ms": round(refresh_time * 1000, 2),
                    "last_successful_refresh": datetime.now(timezone.utc).isoformat(),
                }

                # Check device availability
                is_available = True
                availability_reason = "device_responsive"

                if hasattr(device.status, "switch_state"):
                    if device.status.switch_state == "unavailable":
                        is_available = False
                        availability_reason = "device_unavailable"

                health_check["checks"]["availability"] = {
                    "status": "ok" if is_available else "error",
                    "available": is_available,
                    "reason": availability_reason,
                }

                # Check battery health (if applicable)
                if hasattr(device.status, "battery"):
                    battery_level = device.status.battery
                    battery_health = "good"
                    if battery_level is not None:
                        if battery_level < 10:
                            battery_health = "critical"
                        elif battery_level < 25:
                            battery_health = "low"
                        elif battery_level < 50:
                            battery_health = "medium"

                    health_check["checks"]["battery"] = {
                        "status": (
                            "warning" if battery_health in ["critical", "low"] else "ok"
                        ),
                        "level": battery_level,
                        "health": battery_health,
                    }

                # Check signal strength (if applicable)
                signal_strength = getattr(device.status, "lqi", None) or getattr(
                    device.status, "rssi", None
                )
                if signal_strength is not None:
                    signal_health = "good"
                    if isinstance(signal_strength, (int, float)):
                        if signal_strength < 30:  # Assume LQI scale or weak RSSI
                            signal_health = "poor"
                        elif signal_strength < 60:
                            signal_health = "fair"

                    health_check["checks"]["signal"] = {
                        "status": "warning" if signal_health == "poor" else "ok",
                        "strength": signal_strength,
                        "quality": signal_health,
                    }

                # Determine overall health
                error_checks = [
                    c
                    for c in health_check["checks"].values()
                    if c.get("status") == "error"
                ]
                warning_checks = [
                    c
                    for c in health_check["checks"].values()
                    if c.get("status") == "warning"
                ]

                if error_checks:
                    health_check["overall_health"] = "error"
                elif warning_checks:
                    health_check["overall_health"] = "warning"
                else:
                    health_check["overall_health"] = "ok"

            except Exception as ex:
                health_check["checks"]["connectivity"] = {
                    "status": "error",
                    "error": str(ex),
                    "last_error": datetime.now(timezone.utc).isoformat(),
                }
                health_check["overall_health"] = "error"

            health_check["check_duration_ms"] = round(
                (time.time() - start_time) * 1000, 2
            )
            health_results["checks_performed"].append(health_check)

        # Store health results
        if "diagnostics" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["diagnostics"] = {}
        hass.data[DOMAIN]["diagnostics"]["last_health_check"] = health_results

        # Summary logging
        total_devices = len(health_results["checks_performed"])
        healthy_devices = len(
            [
                c
                for c in health_results["checks_performed"]
                if c["overall_health"] == "ok"
            ]
        )
        warning_devices = len(
            [
                c
                for c in health_results["checks_performed"]
                if c["overall_health"] == "warning"
            ]
        )
        error_devices = len(
            [
                c
                for c in health_results["checks_performed"]
                if c["overall_health"] == "error"
            ]
        )

        _LOGGER.info(
            "Device health check complete: %d total, %d healthy, %d warnings, %d errors",
            total_devices,
            healthy_devices,
            warning_devices,
            error_devices,
        )

        if call.data.get("create_notification", False):
            hass.components.persistent_notification.create(
                f"SmartThings NG Device Health Check Complete\n\n"
                f"Total Devices: {total_devices}\n"
                f"Healthy: {healthy_devices}\n"
                f"Warnings: {warning_devices}\n"
                f"Errors: {error_devices}\n"
                f"Generated: {health_results['timestamp']}",
                title="SmartThings NG Health Check",
                notification_id="smartthingsng_health_check",
            )

    # Register the services
    hass.services.async_register(
        DOMAIN,
        "send_command",
        send_command_service,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
                vol.Optional("component_id", default="main"): cv.string,
                vol.Required("capability"): cv.string,
                vol.Required("command"): cv.string,
                vol.Optional("arguments", default=[]): vol.All(
                    cv.ensure_list, [vol.Any(str, int, float, bool)]
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "refresh_device",
        refresh_device_service,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "execute_scene",
        execute_scene_service,
        schema=vol.Schema(
            {
                vol.Required("scene_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "get_diagnostics",
        get_diagnostics_service,
        schema=vol.Schema(
            {
                vol.Optional("create_notification", default=False): cv.boolean,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "device_health_check",
        device_health_check_service,
        schema=vol.Schema(
            {
                vol.Optional("device_id"): cv.string,
                vol.Optional("check_all", default=False): cv.boolean,
                vol.Optional("create_notification", default=False): cv.boolean,
            }
        ),
    )


class DeviceBroker:
    """Manages an individual SmartThings config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        token,
        smart_app,
        devices: Iterable,
        scenes: Iterable,
    ) -> None:
        """Create a new instance of the DeviceBroker."""
        self._hass = hass
        self._entry = entry
        self._installed_app_id = entry.data[CONF_INSTALLED_APP_ID]
        self._smart_app = smart_app
        self._token = token
        self._event_disconnect = None
        self._regenerate_token_remove = None
        self._assignments = self._assign_capabilities(devices)
        self.devices = {device.device_id: device for device in devices}
        self.scenes = {scene.scene_id: scene for scene in scenes}

    def _assign_capabilities(self, devices: Iterable):
        """Assign platforms to capabilities."""
        assignments = {}
        for device in devices:
            capabilities = device.capabilities.copy()
            slots = {}
            for platform in PLATFORMS:
                platform_module = importlib.import_module(
                    f".{platform}", self.__module__
                )
                if not hasattr(platform_module, "get_capabilities"):
                    continue
                assigned = platform_module.get_capabilities(capabilities)
                if not assigned:
                    continue
                # Draw-down capabilities and set slot assignment
                for capability in assigned:
                    if capability not in capabilities:
                        continue
                    capabilities.remove(capability)
                    slots[capability] = platform
            assignments[device.device_id] = slots
        return assignments

    def connect(self):
        """Connect handlers/listeners for device/lifecycle events."""

        # Setup interval to regenerate the refresh token on a periodic basis.
        # Tokens expire in 30 days and once expired, cannot be recovered.
        async def regenerate_refresh_token(now):
            """Generate a new refresh token and update the config entry."""
            await self._token.refresh(
                self._entry.data[CONF_CLIENT_ID],
                self._entry.data[CONF_CLIENT_SECRET],
            )
            self._hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    CONF_REFRESH_TOKEN: self._token.refresh_token,
                },
            )
            _LOGGER.debug(
                "Regenerated refresh token for installed app: %s",
                self._installed_app_id,
            )

        self._regenerate_token_remove = async_track_time_interval(
            self._hass, regenerate_refresh_token, TOKEN_REFRESH_INTERVAL
        )

        # Connect handler to incoming device events
        self._event_disconnect = self._smart_app.connect_event(self._event_handler)

    def disconnect(self):
        """Disconnects handlers/listeners for device/lifecycle events."""
        if self._regenerate_token_remove:
            self._regenerate_token_remove()
        if self._event_disconnect:
            self._event_disconnect()

    def get_assigned(self, device_id: str, platform: str):
        """Get the capabilities assigned to the platform."""
        slots = self._assignments.get(device_id, {})
        return [key for key, value in slots.items() if value == platform]

    def any_assigned(self, device_id: str, platform: str):
        """Return True if the platform has any assigned capabilities."""
        slots = self._assignments.get(device_id, {})
        return any(value for value in slots.values() if value == platform)

    async def _event_handler(self, req, resp, app):
        """Broker for incoming events."""
        # Do not process events received from a different installed app
        # under the same parent SmartApp (valid use-scenario)
        if req.installed_app_id != self._installed_app_id:
            return

        updated_devices = set()
        for evt in req.events:
            if evt.event_type != EVENT_TYPE_DEVICE:
                continue
            if not (device := self.devices.get(evt.device_id)):
                continue
            device.status.apply_attribute_update(
                evt.component_id,
                evt.capability,
                evt.attribute,
                evt.value,
                data=evt.data,
            )

            # Fire events for buttons
            if (
                evt.capability == Capability.button
                and evt.attribute == Attribute.button
            ):
                data = {
                    "component_id": evt.component_id,
                    "device_id": evt.device_id,
                    "location_id": evt.location_id,
                    "value": evt.value,
                    "name": device.label,
                    "data": evt.data,
                }
                self._hass.bus.async_fire(EVENT_BUTTON, data)
                _LOGGER.debug("Fired button event: %s", data)
            else:
                data = {
                    "location_id": evt.location_id,
                    "device_id": evt.device_id,
                    "component_id": evt.component_id,
                    "capability": evt.capability,
                    "attribute": evt.attribute,
                    "value": evt.value,
                    "data": evt.data,
                }
                _LOGGER.debug("Push update received: %s", data)

            updated_devices.add(device.device_id)

        async_dispatcher_send(self._hass, SIGNAL_SMARTTHINGS_UPDATE, updated_devices)


class SmartThingsEntity(Entity):
    """Defines a SmartThings entity."""

    _attr_should_poll = False

    def __init__(self, device: Device) -> None:
        """Initialize the instance."""
        self._device = device
        self._dispatcher_remove = None
        self._attr_name = device.label
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://account.smartthings.com",
            identifiers={(DOMAIN, device.device_id)},
            manufacturer=device.status.ocf_manufacturer_name,
            model=device.status.ocf_model_number,
            name=device.label,
            hw_version=device.status.ocf_hardware_version,
            sw_version=device.status.ocf_firmware_version,
        )

        # Enhanced diagnostic tracking
        self._last_update_time = None
        self._update_count = 0
        self._error_count = 0
        self._last_error = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Enhanced availability check with diagnostic info
        if hasattr(self._device.status, "switch_state"):
            return self._device.status.switch_state != "unavailable"
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return enhanced diagnostic state attributes."""
        from datetime import datetime, timezone

        attributes = {
            # Core device information
            "device_id": self._device.device_id,
            "device_type": self._device.type,
            "manufacturer": self._device.status.ocf_manufacturer_name,
            "model": self._device.status.ocf_model_number,
            "firmware_version": self._device.status.ocf_firmware_version,
            "hardware_version": self._device.status.ocf_hardware_version,
            # Capability information
            "capabilities": list(self._device.capabilities),
            "capability_count": len(self._device.capabilities),
            "components": (
                list(self._device.components.keys()) if self._device.components else []
            ),
            # Diagnostic information
            "integration_version": "1.7.0",
            "last_update": (
                self._last_update_time.isoformat() if self._last_update_time else None
            ),
            "update_count": self._update_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
            # Health indicators
            "health_status": self._get_health_status(),
        }

        # Add battery information if available
        if hasattr(self._device.status, "battery"):
            battery_level = self._device.status.battery
            attributes["battery_level"] = battery_level
            if battery_level is not None:
                if battery_level < 10:
                    attributes["battery_health"] = "critical"
                elif battery_level < 25:
                    attributes["battery_health"] = "low"
                elif battery_level < 50:
                    attributes["battery_health"] = "medium"
                else:
                    attributes["battery_health"] = "good"

        # Add signal strength if available
        signal_strength = getattr(self._device.status, "lqi", None) or getattr(
            self._device.status, "rssi", None
        )
        if signal_strength is not None:
            attributes["signal_strength"] = signal_strength
            if isinstance(signal_strength, (int, float)):
                if signal_strength < 30:
                    attributes["signal_quality"] = "poor"
                elif signal_strength < 60:
                    attributes["signal_quality"] = "fair"
                else:
                    attributes["signal_quality"] = "good"

        return attributes

    def _get_health_status(self) -> str:
        """Get overall health status of the device."""
        if not self.available:
            return "unavailable"

        # Check for recent errors
        if self._error_count > 0 and self._last_error:
            return "error"

        # Check battery health
        if hasattr(self._device.status, "battery"):
            battery_level = self._device.status.battery
            if battery_level is not None and battery_level < 10:
                return "critical"
            elif battery_level is not None and battery_level < 25:
                return "warning"

        # Check signal strength
        signal_strength = getattr(self._device.status, "lqi", None) or getattr(
            self._device.status, "rssi", None
        )
        if (
            signal_strength is not None
            and isinstance(signal_strength, (int, float))
            and signal_strength < 30
        ):
            return "warning"

        return "ok"

    async def async_update_ha_state(self, force_refresh: bool = False) -> None:
        """Update Home Assistant state with diagnostic tracking."""
        from datetime import datetime, timezone

        try:
            self._last_update_time = datetime.now(timezone.utc)
            self._update_count += 1
            await super().async_update_ha_state(force_refresh)
        except Exception as ex:
            self._error_count += 1
            self._last_error = str(ex)
            _LOGGER.debug("Error updating state for %s: %s", self.entity_id, ex)
            raise

    async def async_added_to_hass(self):
        """Device added to hass."""

        async def async_update_state(devices):
            """Update device state."""
            if self._device.device_id in devices:
                await self.async_update_ha_state(True)

        self._dispatcher_remove = async_dispatcher_connect(
            self.hass, SIGNAL_SMARTTHINGS_UPDATE, async_update_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect the device when removed."""
        if self._dispatcher_remove:
            self._dispatcher_remove()
