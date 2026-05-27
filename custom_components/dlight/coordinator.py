"""DataUpdateCoordinator for the dLight integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import DeviceInfo, DlightClient, DlightError, LampState
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DlightCoordinator(DataUpdateCoordinator[LampState]):
    """Polls the lamp gently and serializes all access through the client."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DlightClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.client = client
        self.device_info: DeviceInfo | None = None

    async def _async_setup(self) -> None:
        try:
            self.device_info = await self.client.query_info()
        except DlightError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> LampState:
        try:
            return await self.client.query_state()
        except DlightError as err:
            raise UpdateFailed(str(err)) from err
