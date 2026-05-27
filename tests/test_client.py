"""Tests for the dLight protocol client."""
from __future__ import annotations

import pytest

from custom_components.dlight.client import (
    DeviceInfo,
    DlightClient,
    LampState,
)


async def test_query_info(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    info = await client.query_info()
    assert info == DeviceInfo(model="GLAMP001", hw_version="1.2", sw_version="3.0.4")


async def test_query_state(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    state = await client.query_state()
    assert state == LampState(on=True, brightness=100, color_temp_kelvin=2600)


async def test_query_state_sends_well_formed_request(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    await client.query_state()
    req = fake_lamp.received[-1]
    assert req["deviceId"] == "0AeLoJZc"
    assert req["commandType"] == "QUERY_DEVICE_STATES"
    assert req["commands"] is None
    assert isinstance(req["commandId"], str)
