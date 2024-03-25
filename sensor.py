import logging


from .const import DOMAIN, CONF_URL, CONF_METERID, CONF_STORED_TOKEN
from energiinfo.api import EnergiinfoClient
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy, UnitOfVolume
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from datetime import timedelta

from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
    PollUpdateMixin,
)


_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the energy sensors."""
    _LOGGER.info(config_entry)
    _LOGGER.info(config_entry.data)

    energiinfo_client = hass.data[DOMAIN][config_entry.entry_id]

    # Fetch metering_points
    # metering_points = energiinfo_client.get_metering_points()
    # if not metering_points:
    #    _LOGGER.error("Failed to fetch metering points")
    #    return

    # metering_points = energiinfo_client.get_metering_points()
    # if not metering_points:
    #    _LOGGER.error("Failed to fetch metering points")
    #    return

    # Add the meter received
    entities = []
    entities.append(
        EnergiinfoSensor(
            energiinfo_client,
            config_entry.data["meter_id"],
            config_entry.data["alias"],
        )
    )

    async_add_entities(entities)
    # if energy_data is None:
    #     _LOGGER.error("Failed to fetch energy data")
    #     return

    # # Create energy sensors based on fetched data
    # entities = []

    # for meter_id, energy_usage in energy_data.items():
    #     entities.append(
    #         EnergiinfoSensor(
    #             config_entry.title, meter_id, energy_usage, api_url, api_token
    #         )
    #     )

    # async_add_entities(entities)


class EnergiinfoSensor(Entity):
    """Representation of an energiinfo sensor."""

    def __init__(
        self,
        energiinfo_client: EnergiinfoClient,
        meter_id: str,
        meter_alias: str,
    ):
        """Initialize the energy sensor."""
        self._meter_alias = meter_alias
        self._meter_id = meter_id
        self._energy_usage = None
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._energiinfo_client = energiinfo_client

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._meter_id}_energy"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = f"{self._meter_id}_energy"

        SCAN_INTERVAL = timedelta(seconds=30)

    # async def async_added_to_hass(self) -> None:
    #     """Run when this Entity has been added to HA."""
    #     # Importantly for a push integration, the module that will be getting updates
    #     # needs to notify HA of changes. The dummy device has a registercallback
    #     # method, so to this we add the 'self.async_write_ha_state' method, to be
    #     # called where ever there are changes.
    #     # The call back registration is done once this entity is registered with HA
    #     # (rather than in the __init__)
    #     _LOGGER.info(f"Added {self._attr_name}:{self._attr_unique_id}")
    #     self._energiinfo_client.register_callback(self.async_write_ha_state)

    # async def async_will_remove_from_hass(self) -> None:
    #     """Entity being removed from hass."""
    #     # The opposite of async_added_to_hass. Remove any registered call backs here.
    #     _LOGGER.info(f"Removed {self._attr_name}:{self._attr_unique_id}")
    #     self._roller.remove_callback(self.async_write_ha_state)

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if api and hub is available."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._meter_alias} Energy Usage"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._energy_usage

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Update the sensor."""
        # Fetch energy data using the EnergiinfoClient
        # period_data = api.get_period_values('107223', '20240225', 'ActiveEnergy', 'hour')
        period_values = await self.hass.async_add_executor_job(
            self._energiinfo_client.get_period_values,
            self._meter_id,
            "2024030723",
            "ActiveEnergy",
            "hour",
        )

        if period_values:
            # Sum up the energy usage for the day
            self._energy_usage = sum(float(value["value"]) for value in period_values)
            _LOGGER.info("Updating energiinfo sensor " + str(self._energy_usage))
        else:
            error_message = await self.hass.async_add_executor_job(
                self._energiinfo_client.getErrorMessage
            )
            _LOGGER.error(
                "Failed to fetch energy data for meter %s: %s",
                self._meter_id,
                error_message,
            )
