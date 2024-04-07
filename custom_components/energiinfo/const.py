"""Constants for the energiinfo integration."""

import logging
from homeassistant.const import Platform

DOMAIN = "energiinfo"
PLATFORMS = [Platform.SENSOR]
LOGGER = logging.getLogger(__package__)

CONF_URL = "url"
CONF_SITEID = "site_id"
CONF_METERID = "meter_id"
CONF_STORED_TOKEN: str = "stored_token"
CONF_DAYS_BACK = "days_back"
CONF_LAST_UPDATE = "last_update"

# How many days back MAXIMUM to calculate
CONF_MAX_DAYS_BACK = 90
