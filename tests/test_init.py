"""Tests for config entry setup/unload."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import CONF_DEVICE_ID, CONF_PORT, DOMAIN


async def test_setup_and_unload(hass: HomeAssistant, fake_lamp):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: fake_lamp.host,
            CONF_PORT: fake_lamp.port,
            CONF_DEVICE_ID: "AbCd1234",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
