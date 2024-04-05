import itertools
import statistics
from datetime import datetime, timedelta

import logging

from .const import DOMAIN, CONF_URL, CONF_METERID, CONF_STORED_TOKEN, CONF_DAYS_BACK
from energiinfo.api import EnergiinfoClient
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util import dt as dtutil

from homeassistant.components.sensor import ENTITY_ID_FORMAT

from homeassistant_historical_sensor import (
    HistoricalSensor,
    HistoricalState,
    PollUpdateMixin,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # noqa DiscoveryInfoType | None
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
        EnergiinfoHistorySensor(
            energiinfo_client,
            config_entry.data["meter_id"],
            config_entry.data["alias"],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_DAYS_BACK],
        )
    )

    async_add_entities(entities)


class EnergiinfoHistorySensor(PollUpdateMixin, HistoricalSensor, SensorEntity):
    """Representation of an energiinfo sensor."""

    #
    # Base clases:
    # - SensorEntity: This is a sensor, obvious
    # - HistoricalSensor: This sensor implements historical sensor methods
    # - PollUpdateMixin: Historical sensors disable poll, this mixing
    #                    reenables poll only for historical states and not for
    #                    present state
    #
    UPDATE_INTERVAL: timedelta = timedelta(hours=2)

    def __init__(
        self,
        energiinfo_client: EnergiinfoClient,
        meter_id: str,
        meter_alias: str,
        password: str,
        username: str,
        days_back: int,
    ):
        """Initialize the energy sensor."""
        self._meter_alias = meter_alias
        self._meter_id = meter_id
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._energiinfo_client = energiinfo_client
        self._username = username
        self._password = password
        self._days_back = days_back
        self._last_update = None

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._meter_id}_energy"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_has_entity_name = True
        self._attr_name = f"{self._meter_alias}"
        self._attr_entity_id = f"sensor.{DOMAIN}_{self._meter_id}"

        self._attr_entity_registry_enabled_default = True
        self._attr_state = None

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
        return self._attr_name
        # return f"{self._meter_alias} Energy Usage"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def statistic_id(self) -> str:
        return self.entity_id

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            "meter_alias": self._meter_alias,
            "meter_id": self._meter_id,
            "days_back": self._days_back,
            "last_update": self._last_update,
        }

    async def async_update_historical(self):
        # Fill `HistoricalSensor._attr_historical_states` with HistoricalState's
        # This functions is equivaled to the `Sensor.async_update` from
        # HomeAssistant core
        #
        # Important: You must provide datetime with tzinfo
        current_time = datetime.now()  # Get current date and time
        previous_day = current_time - timedelta(days=1)  # Subtract one day
        days_back_day = current_time - timedelta(
            days=self._days_back
        )  # Subtract days_back days back
        hist_states = []
        while days_back_day <= previous_day:
            period = days_back_day.strftime("%Y%m%d")
            _LOGGER.info(f"async_update_historical: period={period}")

            # Fetch input data
            input_data = await self.hass.async_add_executor_job(
                self._energiinfo_client.get_period_values,
                self._meter_id,
                period,
                "ActiveEnergy",
                "hour",
            )

            if input_data is None:
                _LOGGER.info("No data found")
                status = await self.hass.async_add_executor_job(
                    self._energiinfo_client.getStatus
                )
                errorMessage = await self.hass.async_add_executor_job(
                    self._energiinfo_client.getErrorMessage
                )
                if errorMessage == "Access denied":
                    _LOGGER.info("Access denied. Will try login again")
                    response = await self.hass.async_add_executor_job(
                        self._energiinfo_client.authenticate,
                        self._username,
                        self._password,
                        "temporary",
                    )
                else:
                    _LOGGER.error(f"Status: {status} Error: {errorMessage}")
                    # Handle case where input_daqta is None
                self._attr_historical_states = []
                return

            # Convert input data into HistoricalState objects
            for data in input_data:
                hist_time = dtutil.as_local(datetime.strptime(data["time"], "%Y%m%d%H"))
                _LOGGER.info(f"last_update={self._last_update},hist_time={hist_time}")
                # Check if the current data's time is higher than the highest_time
                if self._last_update is None or hist_time > self._last_update:
                    _LOGGER.info(
                        f"adding hist last_update={self._last_update},hist_time={hist_time}"
                    )
                    hist = HistoricalState(
                        state=float(data["value"]),
                        dt=hist_time,
                    )
                    hist_states.append(hist)
                    # Check if the current data's time is higher than the highest_time
                    if self._last_update is None or hist.dt > self._last_update:
                        self._last_update = hist.dt

            # Move to the next day
            days_back_day += timedelta(days=1)

        # Fill the historical_states attribute with HistoricalState objects
        self._attr_historical_states = hist_states

    async def async_calculate_statistic_data(
        self, hist_states: list[HistoricalState], *, latest: dict | None = None
    ) -> list[StatisticData]:
        #
        # Group historical states by hour
        # Calculate sum, mean, etc...
        #
        _LOGGER.info(f"Calculating statistics data")
        accumulated = latest["sum"] if latest else 0

        ret = []
        for hist in hist_states:
            mean = hist.state
            partial_sum = hist.state
            accumulated = accumulated + partial_sum

            ret.append(
                StatisticData(
                    start=hist.dt,
                    state=partial_sum,
                    mean=mean,
                    sum=accumulated,
                )
            )
        _LOGGER.info(f"Finished calculating statistics data")

        return ret

    def get_statistic_metadata(self) -> StatisticMetaData:
        #
        # Add sum and mean to base statistics metadata
        # Important: HistoricalSensor.get_statistic_metadata returns an
        # internal source by default.
        #
        meta = super().get_statistic_metadata()
        meta["has_sum"] = True
        # meta["has_mean"] = True
        return meta
