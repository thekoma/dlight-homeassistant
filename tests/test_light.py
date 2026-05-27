"""Tests for the dLight light entity."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import CONF_DEVICE_ID, CONF_PORT, DOMAIN


async def _setup(hass: HomeAssistant, fake_lamp) -> str:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="dLight 0AeLoJZc",
        data={
            CONF_HOST: fake_lamp.host,
            CONF_PORT: fake_lamp.port,
            CONF_DEVICE_ID: "0AeLoJZc",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return "light.dlight_0aelojzc"


async def test_state_reflects_lamp(hass: HomeAssistant, fake_lamp):
    fake_lamp.state = {"on": True, "brightness": 100, "color": {"temperature": 2600}}
    entity_id = await _setup(hass, fake_lamp)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 255  # lamp 100 -> HA 255
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2600


async def test_turn_on_with_brightness(hass: HomeAssistant, fake_lamp):
    entity_id = await _setup(hass, fake_lamp)
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    execs = [r for r in fake_lamp.received if r["commandType"] == "EXECUTE"]
    assert execs[-1]["commands"][0]["brightness"] == 100  # HA 255 -> lamp 100


async def test_turn_on_with_color_temp(hass: HomeAssistant, fake_lamp):
    entity_id = await _setup(hass, fake_lamp)
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )
    execs = [r for r in fake_lamp.received if r["commandType"] == "EXECUTE"]
    assert execs[-1]["commands"] == [{"color": {"temperature": 4000}}]


async def test_turn_off(hass: HomeAssistant, fake_lamp):
    entity_id = await _setup(hass, fake_lamp)
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    execs = [r for r in fake_lamp.received if r["commandType"] == "EXECUTE"]
    assert execs[-1]["commands"] == [{"on": False}]
