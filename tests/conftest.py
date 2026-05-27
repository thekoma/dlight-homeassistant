"""Shared fixtures: a fake dLight TCP server + HA custom-integration enablement."""
from __future__ import annotations

import asyncio
import json
import struct

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in all tests."""
    yield


class FakeLamp:
    """Minimal asyncio server that speaks the dLight protocol."""

    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port: int | None = None
        self._server: asyncio.AbstractServer | None = None
        self.received: list[dict] = []
        self.status = "SUCCESS"          # set to e.g. "ERROR" to simulate failure
        self.response_delay = 0.0         # seconds, to simulate a slow lamp
        self.state = {"on": True, "brightness": 100, "color": {"temperature": 2600}}
        self.info = {"deviceModel": "GLAMP001", "hwVersion": "1.2", "swVersion": "3.0.4"}

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.host, 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        line = await reader.readline()
        req = json.loads(line.decode())
        self.received.append(req)
        if self.response_delay:
            await asyncio.sleep(self.response_delay)
        resp = {"commandId": req["commandId"], "deviceId": req["deviceId"], "status": self.status}
        ctype = req["commandType"]
        if ctype == "QUERY_DEVICE_INFO":
            resp.update(self.info)
        elif ctype == "QUERY_DEVICE_STATES":
            resp["states"] = self.state
        elif ctype == "EXECUTE":
            for cmd in req.get("commands") or []:
                if "on" in cmd:
                    self.state["on"] = cmd["on"]
                if "brightness" in cmd:
                    self.state["brightness"] = cmd["brightness"]
                    self.state["on"] = True
                if "color" in cmd:
                    self.state["color"]["temperature"] = cmd["color"]["temperature"]
            resp["states"] = self.state
        body = json.dumps(resp).encode()
        writer.write(struct.pack(">I", len(body)) + body)
        await writer.drain()
        writer.close()


@pytest.fixture
async def fake_lamp():
    lamp = FakeLamp()
    await lamp.start()
    yield lamp
    await lamp.stop()
