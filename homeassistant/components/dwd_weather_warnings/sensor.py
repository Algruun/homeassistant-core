"""Support for getting statistical data from a DWD Weather Warnings.

Data is fetched from DWD:
https://rcccm.dwd.de/DE/wetter/warnungen_aktuell/objekt_einbindung/objekteinbindung.html

Warnungen vor extremem Unwetter (Stufe 4)
Unwetterwarnungen (Stufe 3)
Warnungen vor markantem Wetter (Stufe 2)
Wetterwarnungen (Stufe 1)
"""

from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ADVANCE_WARNING_SENSOR,
    API_ATTR_WARNING_COLOR,
    API_ATTR_WARNING_DESCRIPTION,
    API_ATTR_WARNING_END,
    API_ATTR_WARNING_HEADLINE,
    API_ATTR_WARNING_INSTRUCTION,
    API_ATTR_WARNING_LEVEL,
    API_ATTR_WARNING_NAME,
    API_ATTR_WARNING_PARAMETERS,
    API_ATTR_WARNING_START,
    API_ATTR_WARNING_TYPE,
    ATTR_LAST_UPDATE,
    ATTR_REGION_ID,
    ATTR_REGION_NAME,
    ATTR_WARNING_COUNT,
    CONF_REGION_NAME,
    CURRENT_WARNING_SENSOR,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import DwdWeatherWarningsCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CURRENT_WARNING_SENSOR,
        name="Current Warning Level",
        icon="mdi:close-octagon-outline",
    ),
    SensorEntityDescription(
        key=ADVANCE_WARNING_SENSOR,
        name="Advance Warning Level",
        icon="mdi:close-octagon-outline",
    ),
)

# Should be removed together with the old YAML configuration.
YAML_MONITORED_CONDITIONS: Final = [CURRENT_WARNING_SENSOR, ADVANCE_WARNING_SENSOR]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_REGION_NAME): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=YAML_MONITORED_CONDITIONS
        ): vol.All(cv.ensure_list, [vol.In(YAML_MONITORED_CONDITIONS)]),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the configurations from YAML to config flows."""
    # Show issue as long as the YAML configuration exists.
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2023.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Deutscher Wetterdienst (DWD) Weather Warnings",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entities from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            DwdWeatherWarningsSensor(coordinator, entry, description)
            for description in SENSOR_TYPES
        ],
        True,
    )


class DwdWeatherWarningsSensor(
    CoordinatorEntity[DwdWeatherWarningsCoordinator], SensorEntity
):
    """Representation of a DWD-Weather-Warnings sensor."""

    _attr_attribution = "Data provided by DWD"

    def __init__(
        self,
        coordinator: DwdWeatherWarningsCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a DWD-Weather-Warnings sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_name = f"{DEFAULT_NAME} {entry.title} {description.name}"
        self._attr_unique_id = f"{entry.unique_id}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=f"{DEFAULT_NAME} {entry.title}"
        )

        self.api = coordinator.api

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            return self.api.current_warning_level

        return self.api.expected_warning_level

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        data = {
            ATTR_REGION_NAME: self.api.warncell_name,
            ATTR_REGION_ID: self.api.warncell_id,
            ATTR_LAST_UPDATE: self.api.last_update,
        }

        if self.entity_description.key == CURRENT_WARNING_SENSOR:
            searched_warnings = self.api.current_warnings
        else:
            searched_warnings = self.api.expected_warnings

        data[ATTR_WARNING_COUNT] = len(searched_warnings)

        for i, warning in enumerate(searched_warnings, 1):
            data[f"warning_{i}_name"] = warning[API_ATTR_WARNING_NAME]
            data[f"warning_{i}_type"] = warning[API_ATTR_WARNING_TYPE]
            data[f"warning_{i}_level"] = warning[API_ATTR_WARNING_LEVEL]
            data[f"warning_{i}_headline"] = warning[API_ATTR_WARNING_HEADLINE]
            data[f"warning_{i}_description"] = warning[API_ATTR_WARNING_DESCRIPTION]
            data[f"warning_{i}_instruction"] = warning[API_ATTR_WARNING_INSTRUCTION]
            data[f"warning_{i}_start"] = warning[API_ATTR_WARNING_START]
            data[f"warning_{i}_end"] = warning[API_ATTR_WARNING_END]
            data[f"warning_{i}_parameters"] = warning[API_ATTR_WARNING_PARAMETERS]
            data[f"warning_{i}_color"] = warning[API_ATTR_WARNING_COLOR]

            # Dictionary for the attribute containing the complete warning.
            warning_copy = warning.copy()
            warning_copy[API_ATTR_WARNING_START] = data[f"warning_{i}_start"]
            warning_copy[API_ATTR_WARNING_END] = data[f"warning_{i}_end"]
            data[f"warning_{i}"] = warning_copy

        return data

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self.api.data_valid
