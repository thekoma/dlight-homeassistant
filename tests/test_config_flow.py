"""Tests for the dLight config flow."""
from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.client import DlightConnectionError
from custom_components.dlight.config_flow import device_id_from_name
from custom_components.dlight.const import (
    CONF_DEVICE_ID,
    CONF_MAC,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

# Note: SOURCE_ZEROCONF, ZeroconfServiceInfo, device_id_from_name and CONF_MAC are
# used by the zeroconf tests appended in Task 9.


@pytest.fixture
def mock_validate():
    """Patch the client used by the config flow and coordinator so no network is needed."""
    with (
        patch("custom_components.dlight.config_flow.DlightClient") as mock_cf_client,
        patch("custom_components.dlight.DlightClient") as mock_init_client,
    ):
        # Config-flow validation client
        cf_instance = mock_cf_client.return_value
        cf_instance.query_info = AsyncMock(return_value=None)

        # Coordinator client (used during async_setup_entry after CREATE_ENTRY)
        from custom_components.dlight.client import DeviceInfo, LampState
        init_instance = mock_init_client.return_value
        init_instance.query_info = AsyncMock(
            return_value=DeviceInfo(
                model="GLAMP001",
                hw_version="1.2",
                sw_version="3.0.4",
            )
        )
        init_instance.query_state = AsyncMock(
            return_value=LampState(on=True, brightness=100, color_temp_kelvin=4000)
        )

        yield cf_instance


async def test_user_flow_success(hass: HomeAssistant, mock_validate):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_DEVICE_ID: "AbCd1234"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "1.2.3.4", CONF_DEVICE_ID: "AbCd1234"}
    assert result["result"].unique_id == "AbCd1234"


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_validate):
    mock_validate.query_info.side_effect = DlightConnectionError("nope")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_DEVICE_ID: "AbCd1234"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant, mock_validate):
    MockConfigEntry(
        domain=DOMAIN, unique_id="AbCd1234",
        data={CONF_HOST: "x", CONF_DEVICE_ID: "AbCd1234"},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_DEVICE_ID: "AbCd1234"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="AbCd1234",
        data={CONF_HOST: "x", CONF_DEVICE_ID: "AbCd1234"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 60


def test_device_id_from_name():
    assert device_id_from_name("GLAMP_AbCd1234._ged7._tcp.local.") == "AbCd1234"
    assert device_id_from_name("glamp_AbCd1234._ged7._tcp.local.") == "AbCd1234"


def _discovery() -> ZeroconfServiceInfo:
    # ZeroconfServiceInfo in this HA version requires IPv4Address/IPv6Address objects,
    # not plain strings, for ip_address and ip_addresses.
    return ZeroconfServiceInfo(
        ip_address=IPv4Address("1.2.3.4"),
        ip_addresses=[IPv4Address("1.2.3.4")],
        port=80,
        hostname="GLAMP_AbCd1234.local.",
        type="_ged7._tcp.local.",
        name="GLAMP_AbCd1234._ged7._tcp.local.",
        properties={"mac": "AABBCCDDEEFF", "model": "GLAMP001"},
    )


async def test_zeroconf_flow_success(hass: HomeAssistant, mock_validate):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == "AbCd1234"
    assert result["data"][CONF_MAC] == "AABBCCDDEEFF"
    assert result["result"].unique_id == "AbCd1234"
