"""The energiinfo integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from energiinfo.api import EnergiinfoClient

from .const import DOMAIN, CONF_URL, CONF_SITEID, CONF_STORED_TOKEN

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up energiinfo from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    api = EnergiinfoClient(
        config_entry.data["url"],
        config_entry.data["site_id"],
        config_entry.data["stored_token"],
    )
    # Verifies the token
    # token = await hass.async_add_executor_job(api.get_access_token())

    hass.data[DOMAIN][config_entry.entry_id] = api

    # if token is not None:
    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]
    # Logout
    response = await hass.async_add_executor_job(api.logout)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
