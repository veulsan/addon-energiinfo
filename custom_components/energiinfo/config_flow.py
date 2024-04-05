"""Config flow for energiinfo integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from energiinfo.api import EnergiinfoClient
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_SITEID,
    CONF_METERID,
    CONF_STORED_TOKEN,
    CONF_DAYS_BACK,
)

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_SITEID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DAYS_BACK): int,
    }
)

STEP_RECONF_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DAYS_BACK): int,
    }
)

# Define the schema for validating user input
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_METERID): str,
    }
)


class EnergiinfoOptionsConfigFlow(OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            _LOGGER.debug(f"{DOMAIN} user input in option flow : %s", user_input)
            return self.async_create_entry(
                title=config_entry[CONF_METERID], data=user_input
            )

        return self.async_show_form(step_id="init", data_schema=self.schema)


class EnergiinfoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for energiinfo."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.info("Initializing")

    async def authenticate(
        self, username: str, password: str
    ) -> tuple[bool, dict[str, Any]]:
        """Get the QR code."""
        token = await self.hass.async_add_executor_job(
            self.__api.authenticate, username, password
        )
        self.__token = token
        if self.__api.getStatus() == "ERR":
            _LOGGER.info(self.__api.getErrorMessage)
            raise InvalidAuth
        return self.__api.getStatus()

    async def get_meter_ids(self) -> tuple[bool, dict[str, Any]]:
        """Get the meterid"""
        meter_list = await self.hass.async_add_executor_job(
            self.__api.get_metering_points
        )
        return self.__api.getStatus(), meter_list

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.__apiurl = user_input[CONF_URL]
                self.__siteid = user_input[CONF_SITEID]
                self.__username = user_input[CONF_USERNAME]
                self.__password = user_input[CONF_PASSWORD]
                self.__days_back = user_input[CONF_DAYS_BACK]
                self.__api = EnergiinfoClient(
                    user_input[CONF_URL], user_input[CONF_SITEID]
                )
                status = await self.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Return the form of the next step.
                return await self.async_step_meter()
                # return self.async_create_entry(
                #    title=user_input[CONF_USERNAME], data=user_input
                # )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_confirm(self, user_input=None):
        """Handle the confirmation step."""
        if user_input is not None:
            # User confirmed, finish the flow
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        # User did not confirm, return to the previous step
        return self.async_show_form(step_id="confirm", data_schema=DATA_SCHEMA)

    async def async_step_meter(self, user_input: Dict[str, Any] = None):
        """Handle meter selection."""
        # Extract meter information from input
        # token = user_input.get("token")
        success, meters = await self.get_meter_ids()

        meter_choices = {
            meter["meteringpoint_id"]: meter["alias"].replace("\r\n", ",")
            for meter in meters
        }
        if not meter_choices:
            return self.async_abort(reason="no_meters")

        # Generate a list of available meters for the user to choose from
        meter_schema = vol.Schema(vol.In(meter_choices))
        if user_input is not None:
            # User has selected a meter, finish the flow
            meter_id = user_input["meter_id"]
            meter_alias = meter_choices[meter_id]
            return self.async_create_entry(
                title=meter_alias,
                data={
                    "meter_id": meter_id,
                    "alias": meter_alias,
                    CONF_STORED_TOKEN: self.__token,
                    CONF_URL: self.__apiurl,
                    CONF_SITEID: self.__siteid,
                    CONF_USERNAME: self.__username,
                    CONF_PASSWORD: self.__password,
                    CONF_DAYS_BACK: self.__days_back,
                },
            )

        # Display meter selection form
        return self.async_show_form(
            step_id="meter",
            data_schema=vol.Schema(
                {
                    vol.Required("meter_id", description="Select a meter"): vol.In(
                        meter_choices
                    )
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] = {}
        assert self.config_entry
        # mappingproxy({'meter_id': '107223', 'alias': 'Skolvägen 8,845 95 Rätan', 'stored_token': 'MQAzADoAMwA5ADQANwA2ADYAOgA0ADcAOAAwADMANgAzAEUAMwBDADMARgBDADUARQA2ADAAMAA3ADIAQQA2AEYARgA4AEYARgAzAEIANgBDAEQANABDAEUAMwA4ADgANgBDAA==', 'url': 'https://api4.energiinfo.se', 'site_id': '13', 'username': '334946', 'password': '50514500', 'days_back': 30})
        # hass.config_entries.async_update_entry(config_entry, data=new, minor_version=3, version=1)

        if user_input is not None:
            days_back: int = user_input[CONF_DAYS_BACK]
            old_days_back = self.config_entry.data[CONF_DAYS_BACK]
            _LOGGER.info("Changes days_back from {old_days_back} to {days_back}")
            # Update data1 with data from data2
            user_input = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
            # entity_reg = er.async_get(self.hass)
            # if entity := entity_reg.async_get_entity_id(
            #    "sensor", DOMAIN, self.config_entry.data["alias"]
            # ):
            #    entity_reg.async_update_entity(entity, new_unique_id=f"{lat}, {lon}")
            # if await async_check_location(self.hass, lon, lat):
            #     unique_id = f"{lat}-{lon}"
            #     await self.async_set_unique_id(unique_id)
            #     self._abort_if_unique_id_configured()

            #     old_lat = self.config_entry.data[CONF_LOCATION][CONF_LATITUDE]
            #     old_lon = self.config_entry.data[CONF_LOCATION][CONF_LONGITUDE]

            #     device_reg = dr.async_get(self.hass)
            #     if device := device_reg.async_get_device(
            #         identifiers={(DOMAIN, f"{old_lat}, {old_lon}")}
            #     ):
            #         device_reg.async_update_device(
            #             device.id, new_identifiers={(DOMAIN, f"{lat}, {lon}")}
            #         )

            # return self.async_update_reload_and_abort(
            #     self.config_entry,
            #     unique_id=unique_id,
            #     data={**self.config_entry.data, **user_input},
            #     reason="reconfigure_successful",
        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=STEP_RECONF_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
