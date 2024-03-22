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
