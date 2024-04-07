# addon-energiinfo
# Home assistant Energy Sensor for Energiinfo API
Custom component using [HistorySensor](https://github.com/ldotlopez/ha-historical-sensor/tree/main) to create a history Energy sensor based on Energiinfo API

# Install via HACS
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=https%3A%2F%2Fgithub.com%2Fveulsan%2Faddon-energiinfo&category=integration&owner=veulsan)

# Setup
After successful installation via HACS you now add your own Energiinfo sensor which will start collecting Energy data and create historical statistics based on how many days back you choose.

![Alt text](Add_Sensor.png?raw=true "Add Sensor")

[!NOTE]
If days back is > 90 DAYS it will start collecting in chunks of 90 days every minute until todays date is met. Once this condition is met it will update every 2 hours.

[!NOTE]
This is an historical sensor it is not meant for current Energy data, as this is not currently provided by the API.
