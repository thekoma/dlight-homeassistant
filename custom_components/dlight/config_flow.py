"""Config flow for the dLight integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .client import DlightClient, DlightError
from .const import (
    CONF_DEVICE_ID,
    CONF_MAC,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    GLAMP_PREFIX,
    MIN_SCAN_INTERVAL,
)


def device_id_from_name(name: str) -> str:
    """Extract the device id from a zeroconf instance name like 'GLAMP_<id>...'."""
    instance = name.split(".", 1)[0]
    if instance.upper().startswith(GLAMP_PREFIX):
        return instance[len(GLAMP_PREFIX):]
    return instance


async def _validate(host: str, device_id: str) -> None:
    client = DlightClient(host, device_id, port=DEFAULT_PORT)
    await client.query_info()


class DlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dLight."""

    def __init__(self) -> None:
        self._host: str | None = None
        self._device_id: str | None = None
        self._mac: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            try:
                await _validate(host, device_id)
            except DlightError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"dLight {device_id}",
                    data={CONF_HOST: host, CONF_DEVICE_ID: device_id},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): str, vol.Required(CONF_DEVICE_ID): str}
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        self._host = discovery_info.host
        self._device_id = device_id_from_name(discovery_info.name)
        self._mac = discovery_info.properties.get("mac")
        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        try:
            await _validate(self._host, self._device_id)
        except DlightError:
            return self.async_abort(reason="cannot_connect")
        self.context["title_placeholders"] = {"name": f"dLight {self._device_id}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._host is not None and self._device_id is not None
        if user_input is not None:
            data: dict[str, Any] = {
                CONF_HOST: self._host,
                CONF_DEVICE_ID: self._device_id,
            }
            if self._mac:
                data[CONF_MAC] = self._mac
            return self.async_create_entry(title=f"dLight {self._device_id}", data=data)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": f"dLight {self._device_id}"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> DlightOptionsFlow:
        return DlightOptionsFlow()


class DlightOptionsFlow(OptionsFlow):
    """Handle dLight options (poll interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
                    )
                }
            ),
        )
