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


async def test_set_on_sends_boolean(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    await client.set_on(False)
    assert fake_lamp.received[-1]["commands"] == [{"on": False}]


async def test_set_brightness_includes_on_true(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    await client.set_brightness(50)
    assert fake_lamp.received[-1]["commands"] == [{"on": True, "brightness": 50}]


async def test_set_brightness_clamped_to_1_100(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    await client.set_brightness(999)
    assert fake_lamp.received[-1]["commands"][0]["brightness"] == 100
    await client.set_brightness(0)
    assert fake_lamp.received[-1]["commands"][0]["brightness"] == 1


async def test_set_temperature_clamped_to_range(fake_lamp):
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    await client.set_temperature(9000)
    assert fake_lamp.received[-1]["commands"] == [{"color": {"temperature": 6000}}]
    await client.set_temperature(1000)
    assert fake_lamp.received[-1]["commands"] == [{"color": {"temperature": 2600}}]


import asyncio

from custom_components.dlight.client import (
    DlightConnectionError,
    DlightProtocolError,
)


async def test_connection_error_when_nothing_listening(socket_enabled):
    client = DlightClient("127.0.0.1", "0AeLoJZc", port=1, timeout=2.0)
    with pytest.raises(DlightConnectionError):
        await client.query_state()


async def test_non_success_status_raises(fake_lamp):
    fake_lamp.status = "ERROR"
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    with pytest.raises(DlightProtocolError):
        await client.query_state()


async def test_commands_are_serialized(fake_lamp):
    """The lock must prevent overlapping connections to the one-connection lamp."""
    fake_lamp.response_delay = 0.2
    client = DlightClient(fake_lamp.host, "0AeLoJZc", port=fake_lamp.port)
    await asyncio.gather(
        client.query_state(),
        client.query_state(),
        client.set_on(True),
    )
    # If serialized, the fake server handled them one at a time without error.
    assert len(fake_lamp.received) == 3
