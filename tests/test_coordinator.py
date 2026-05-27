"""Tests for DlightCoordinator."""
from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.client import DlightClient, DlightConnectionError, LampState
from custom_components.dlight.const import DOMAIN
from custom_components.dlight.coordinator import DlightCoordinator


def _entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data={"host": "h", "device_id": "AbCd1234"})


async def test_coordinator_setup_and_update(hass: HomeAssistant, fake_lamp):
    entry = _entry()
    entry.add_to_hass(hass)
    # Newer HA requires SETUP_IN_PROGRESS state for async_config_entry_first_refresh.
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    client = DlightClient(fake_lamp.host, "AbCd1234", port=fake_lamp.port)
    coordinator = DlightCoordinator(hass, entry, client, scan_interval=30)
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.device_info.model == "GLAMP001"
    assert coordinator.data == LampState(on=True, brightness=100, color_temp_kelvin=2600)


async def test_coordinator_update_failure(hass: HomeAssistant, socket_enabled):
    entry = _entry()
    entry.add_to_hass(hass)
    # Newer HA requires SETUP_IN_PROGRESS state for async_config_entry_first_refresh.
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    client = DlightClient("127.0.0.1", "AbCd1234", port=1, timeout=2.0)
    coordinator = DlightCoordinator(hass, entry, client, scan_interval=30)
    with pytest.raises(Exception):  # ConfigEntryNotReady wraps the first-refresh failure
        await coordinator.async_config_entry_first_refresh()
