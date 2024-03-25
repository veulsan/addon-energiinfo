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

from .const import DOMAIN, CONF_URL, CONF_SITEID, CONF_METERID, CONF_STORED_TOKEN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_SITEID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
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
            return self.async_create_entry(title="", data=user_input)

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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
