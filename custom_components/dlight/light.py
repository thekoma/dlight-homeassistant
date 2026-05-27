"""Light platform for the dLight integration."""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import DlightConfigEntry
from .client import DlightError
from .const import (
    BRIGHTNESS_SCALE,
    CONF_DEVICE_ID,
    CONF_MAC,
    DOMAIN,
    MAX_KELVIN,
    MIN_KELVIN,
)
from .coordinator import DlightCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DlightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([DlightLight(entry)])


class DlightLight(CoordinatorEntity[DlightCoordinator], LightEntity):
    """A Google dLight as a color-temperature light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(self, entry: DlightConfigEntry) -> None:
        coordinator = entry.runtime_data
        super().__init__(coordinator)
        device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = device_id
        info = coordinator.device_info
        mac = entry.data.get(CONF_MAC)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer="Google",
            model=info.model if info else None,
            sw_version=info.sw_version if info else None,
            hw_version=info.hw_version if info else None,
            connections={(CONNECTION_NETWORK_MAC, format_mac(mac))} if mac else set(),
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.on

    @property
    def brightness(self) -> int | None:
        return value_to_brightness(BRIGHTNESS_SCALE, self.coordinator.data.brightness)

    @property
    def color_temp_kelvin(self) -> int:
        return self.coordinator.data.color_temp_kelvin

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        new = self.coordinator.data
        try:
            if ATTR_BRIGHTNESS in kwargs:
                value = math.ceil(brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS]))
                await client.set_brightness(value)
                new = replace(new, on=True, brightness=value)
            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kwargs[ATTR_COLOR_TEMP_KELVIN]))
                await client.set_temperature(kelvin)
                new = replace(new, color_temp_kelvin=kelvin)
            if ATTR_BRIGHTNESS not in kwargs and ATTR_COLOR_TEMP_KELVIN not in kwargs:
                await client.set_on(True)
                new = replace(new, on=True)
        except DlightError as err:
            raise HomeAssistantError(f"Failed to control dLight: {err}") from err
        self.coordinator.async_set_updated_data(new)  # optimistic

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.set_on(False)
        except DlightError as err:
            raise HomeAssistantError(f"Failed to control dLight: {err}") from err
        self.coordinator.async_set_updated_data(replace(self.coordinator.data, on=False))
