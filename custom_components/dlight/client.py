"""Async client for the Google dLight local TCP/JSON protocol."""
from __future__ import annotations

import asyncio
import json
import random
import struct
from dataclasses import dataclass

from .const import DEFAULT_PORT, DEFAULT_TIMEOUT, MAX_KELVIN, MIN_KELVIN


class DlightError(Exception):
    """Base error for the dLight client."""


class DlightConnectionError(DlightError):
    """Could not connect to / read from the lamp."""


class DlightTimeoutError(DlightError):
    """The lamp did not respond in time."""


class DlightProtocolError(DlightError):
    """The lamp returned a malformed response or a non-success status."""


@dataclass(frozen=True)
class LampState:
    """A snapshot of the lamp's state."""

    on: bool
    brightness: int  # lamp scale 1-100
    color_temp_kelvin: int


@dataclass(frozen=True)
class DeviceInfo:
    """Static device information."""

    model: str
    hw_version: str
    sw_version: str


class DlightClient:
    """Talks to a single dLight lamp.

    The lamp sustains only one connection at a time, so every command takes a
    per-client lock and uses its own short-lived connection.
    """

    def __init__(
        self,
        host: str,
        device_id: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._device_id = device_id
        self._port = port
        self._timeout = timeout
        self._lock = asyncio.Lock()

    async def _execute(self, command_type: str, commands: list[dict] | None = None) -> dict:
        payload = {
            "commandId": str(random.randint(1, 2**62)),
            "deviceId": self._device_id,
            "commandType": command_type,
            "commands": commands,
        }
        data = (json.dumps(payload) + "\n").encode()
        async with self._lock:
            try:
                async with asyncio.timeout(self._timeout):
                    reader, writer = await asyncio.open_connection(self._host, self._port)
                    try:
                        writer.write(data)
                        await writer.drain()
                        header = await reader.readexactly(4)
                        (length,) = struct.unpack(">I", header)
                        body = await reader.readexactly(length)
                    finally:
                        writer.close()
                        await writer.wait_closed()
            except TimeoutError as err:
                raise DlightTimeoutError(f"timeout talking to {self._host}") from err
            except (OSError, asyncio.IncompleteReadError) as err:
                raise DlightConnectionError(str(err)) from err
        try:
            resp = json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            raise DlightProtocolError("could not decode response") from err
        if resp.get("status") != "SUCCESS":
            raise DlightProtocolError(f"non-success status: {resp.get('status')!r}")
        return resp

    async def query_info(self) -> DeviceInfo:
        resp = await self._execute("QUERY_DEVICE_INFO")
        return DeviceInfo(
            model=resp.get("deviceModel", ""),
            hw_version=resp.get("hwVersion", ""),
            sw_version=resp.get("swVersion", ""),
        )

    async def query_state(self) -> LampState:
        resp = await self._execute("QUERY_DEVICE_STATES")
        states = resp.get("states") or {}
        color = states.get("color") or {}
        return LampState(
            on=bool(states.get("on")),
            brightness=int(states.get("brightness", 0)),
            color_temp_kelvin=int(color.get("temperature", 0)),
        )

    async def set_on(self, on: bool) -> None:
        await self._execute("EXECUTE", [{"on": on}])

    async def set_brightness(self, brightness: int) -> None:
        brightness = max(1, min(100, brightness))
        await self._execute("EXECUTE", [{"on": True, "brightness": brightness}])

    async def set_temperature(self, kelvin: int) -> None:
        kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
        await self._execute("EXECUTE", [{"color": {"temperature": kelvin}}])
