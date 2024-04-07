import itertools
import statistics
from datetime import datetime, timedelta
import pytz

import logging

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_METERID,
    CONF_STORED_TOKEN,
    CONF_DAYS_BACK,
    CONF_LAST_UPDATE,
    CONF_MAX_DAYS_BACK,
)
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
from homeassistant.helpers.event import track_time_interval
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
    _LOGGER.debug(f"Setting up Energiinfo sensor {config_entry.data}")

    energiinfo_client = hass.data[DOMAIN][config_entry.entry_id]

    # Add the meter received
    last_update = config_entry.data.get(
        CONF_LAST_UPDATE
    )  # Get CONF_LAST_UPDATE, return None if not found

    entities = []
    entities.append(
        EnergiinfoHistorySensor(
            energiinfo_client,
            config_entry.data["meter_id"],
            config_entry.data["alias"],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_DAYS_BACK],
            last_update
            if last_update is not None
            else None,  # Assign None if last_update is None
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
    UPDATE_INTERVAL: timedelta = timedelta(minutes=1)

    def __init__(
        self,
        energiinfo_client: EnergiinfoClient,
        meter_id: str,
        meter_alias: str,
        password: str,
        username: str,
        days_back: int,
        last_update: str,
    ):
        """Initialize the energy sensor."""
        self._meter_alias = meter_alias
        self._meter_id = meter_id
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._energiinfo_client = energiinfo_client
        self._username = username
        self._password = password
        self._days_back = days_back
        self._timzeone = pytz.timezone("CET")  # Get the timezone object for CET

        _LOGGER.info(f"last_update={last_update}")
        if last_update is not None:
            self._last_update = datetime.fromisoformat(
                str(last_update)
            )  # Convert string to datetime object
        else:
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
        # Timezone info of your timezone aware variable
        # Create a datetime object with timezone information
        current_time = self._timzeone.localize(datetime.now())
        previous_day = current_time - timedelta(days=1)  # Subtract one day

        # Initialize days_back to the maximum number of days or 1, depending on last_update
        if self._last_update is None:
            days_back_day = min(
                current_time - timedelta(days=CONF_MAX_DAYS_BACK),
                current_time - timedelta(days=self._days_back),
            )
        else:
            days_back_day = min(self._last_update, previous_day)
            if previous_day < self._last_update:
                _LOGGER.info("Update interval changed to 2 Hours")
                self.UPDATE_INTERVAL = timedelta(hours=2)

        # Calculate the end date for the current iteration
        end_date = min(
            days_back_day + timedelta(days=CONF_MAX_DAYS_BACK),
            previous_day + timedelta(days=1),
        )

        if self._last_update is not None:
            if self._last_update < current_time:
                current_time = self._last_update + timedelta(hours=1)

        previous_day = current_time - timedelta(days=1)  # Subtract one day

        self.config_entry = self.hass.config_entries.async_get_entry(
            self.registry_entry.config_entry_id
        )

        hist_states = []
        period = (
            (days_back_day + timedelta(hours=1)).strftime("%Y%m%d%H")
            + "-"
            + end_date.strftime("%Y%m%d%H")
        )
        _LOGGER.info(f"Updating historical data between {period}")

        # Fetch input data
        input_data = await self.hass.async_add_executor_job(
            self._energiinfo_client.get_period_values,
            self._meter_id,
            period,
            "ActiveEnergy",
            "hour",
        )
        last_update_changed = False

        if input_data is None:
            _LOGGER.debug("No new data found")
            status = await self.hass.async_add_executor_job(
                self._energiinfo_client.getStatus
            )
            errorMessage = await self.hass.async_add_executor_job(
                self._energiinfo_client.getErrorMessage
            )

            if errorMessage == "Access denied":
                _LOGGER.info("Access denied. Will try login again")
                token = await self.hass.async_add_executor_job(
                    self._energiinfo_client.authenticate,
                    self._username,
                    self._password,
                    "temporary",
                )
                self.__token = token
                user_input = {CONF_STORED_TOKEN: token}
                # Update token
                user_input = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )
                _LOGGER.debug(f"Updated {CONF_STORED_TOKEN} to {token}")
            else:
                _LOGGER.error(f"Status: {status} Error: {errorMessage}")
                # Handle case where input_daqta is None
            self._attr_historical_states = []
        elif len(input_data) == 0:
            status = await self.hass.async_add_executor_job(
                self._energiinfo_client.getStatus
            )
            if status == "OK":
                last_update_changed = True
                self._last_update = end_date
        else:
            # Convert input data into HistoricalState objects
            for data in input_data:
                hist_time = dtutil.as_local(datetime.strptime(data["time"], "%Y%m%d%H"))
                # Check if the current data's time is higher than the highest_time
                if self._last_update is None or hist_time > self._last_update:
                    hist = HistoricalState(
                        state=float(data["value"]),
                        dt=hist_time,
                    )
                    hist_states.append(hist)
                    _LOGGER.debug(f"Added HistoricalState({hist.state},{hist.dt})")
                    # Check if the current data's time is higher than the highest_time
                    if self._last_update is None:
                        self._last_update = hist.dt
                        last_update_changed = True
                    elif hist.dt > self._last_update:
                        self._last_update = hist.dt
                        last_update_changed = True

        if last_update_changed:
            user_input = {"last_update": self._last_update}
            # Update with last_update
            user_input = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )
            _LOGGER.info(f"Updated last_update to {self._last_update}")

        # Fill the historical_states attribute with HistoricalState objects
        self._attr_historical_states = hist_states

    async def async_calculate_statistic_data(
        self, hist_states: list[HistoricalState], *, latest: dict | None = None
    ) -> list[StatisticData]:
        #
        # Group historical states by hour
        # Calculate sum, mean, etc...
        #
        _LOGGER.info(f"Will calculate statistics data for historical states")
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
        _LOGGER.debug(f"Finished calculating statistics data")

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
