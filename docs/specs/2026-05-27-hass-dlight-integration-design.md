# Design: `dlight-homeassistant` — native Home Assistant integration for the Google dLight

- **Date:** 2026-05-27
- **Status:** Approved design, pending spec review
- **Target repo:** `dlight-homeassistant` (new, dedicated, HACS-ready)
- **Supersedes:** the `dlight2mqtt` Go bridge (kept for reference; protocol captured in its `PROTOCOL.md`)

## 1. Context & motivation

Today a Go process (`dlight2mqtt`) bridges the lamp to Home Assistant over MQTT.
It works but has three problems the owner wants to solve:

1. **Operational overhead** — a separate container must be kept running and
   monitored.
2. **Polling crashes the lamp** (rarely, lately very rarely). Root cause
   identified during design: the Go bridge polls every **1s**, but a single
   `QUERY_DEVICE_STATES` round-trip takes **~1.2s** on the current firmware, so
   connections pile up back-to-back on a device that only sustains **one
   connection at a time**.
3. **Color-temperature floor** — originally believed to reach ~2004K. Verified
   empirically (see §3): the real range is **2600K–6000K**, matching the Go
   code's existing clamps. No range change is needed; the 2004K figure was a
   misconception.

A native HA custom integration removes the bridge entirely (the protocol client
becomes an in-process asyncio module), lets HA drive the lamp directly, and lets
us redesign the polling to stop stressing the device.

## 2. Goals / Non-goals

**Goals**
- A HACS-installable custom integration (`domain: dlight`) exposing the lamp as a
  `light` entity with on/off, brightness, and color temperature.
- UI setup via Config Flow, with **zeroconf auto-discovery** plus manual entry.
- A polling strategy that does not crash the lamp.
- Correct color-temperature range (min 2004K).
- No external runtime dependencies, no container.

**Non-goals (v1)**
- Persistent/long-lived connection to the lamp (kept as a future experiment —
  see §13).
- Effects, transitions, or RGB color (the lamp is color-temp only).
- Publishing the protocol client as a separate PyPI package (vendored instead).

## 3. Findings (verified on the live device, firmware 3.0.4)

**mDNS / discovery**
- Service type: **`_ged7._tcp.local.`**
- Instance name: **`GLAMP_<deviceId>`** (e.g. `GLAMP_0AeLoJZc`) — note the
  underscore; the Go code's `GLAMP-<id>` (hyphen) hostname never resolved, which
  is why an explicit IP was always configured.
- SRV advertises `GLAMP_<id>.local:80` (an HTTP/setup endpoint). **The control
  protocol is on TCP 3333**, which we use instead of the advertised port.
- TXT record fields: `HW`, `MAC`, `FW`, `Model`
  (observed: `HW=1.2 MAC=50D21301C7B2 FW=3.0.4 Model=GLAMP001`).

**Identity / reachability**
- The lamp at `192.168.85.88` is confirmed via ARP (`50:d2:13:01:c7:b2`, matches
  the TXT `MAC`) and via a live protocol query returning its own
  `deviceId`/`Model`.
- It **does** respond to ICMP, with high/variable latency (55–200ms).

**Protocol** (matches `dlight2mqtt/PROTOCOL.md` exactly on FW 3.0.4)
- `QUERY_DEVICE_INFO` → `{deviceModel, hwVersion, swVersion, status}` (~210ms).
- `QUERY_DEVICE_STATES` → `{states:{on, brightness, color:{temperature}}, status}`
  (~1.2s — the device is slow; the client must use generous timeouts).
- Framing is asymmetric: send `JSON\n` (no length prefix); receive a 4-byte
  big-endian `uint32` length prefix + JSON body.

**Color temperature & physical-control behavior** (measured via the touch ring)
- Warmest = **2600K**, coolest = **6000K** (both match the Go clamps
  `[2600, 6000]`). The earlier ~2004K belief was incorrect.
- Changes made via the **physical control are reflected** in
  `QUERY_DEVICE_STATES` (moving the ring warm→cold changed the reported value
  2600→6000). This confirms polling picks up out-of-band changes — the premise of
  Approach A.
- **Brightness** physical range is **5–100**: the ring's minimum is 5 and does
  **not** turn the lamp off. Brightness also reflects physical changes
  (100 → 5 observed).

## 4. Architecture overview

```
Home Assistant
  └─ custom_components/dlight/
       config_flow.py ──(zeroconf/_ged7 + manual)──┐
       __init__.py ── creates ──> coordinator.py    │ sets host, device_id
                                       │ polls       │
                                       ▼             ▼
                                   client.py ──TCP 3333──> dLight lamp
                                       ▲
       light.py (CoordinatorEntity) ───┘ reads state / sends commands
```

Each unit has one responsibility and a narrow interface:
- `client.py` — speaks the wire protocol; knows nothing about HA.
- `coordinator.py` — schedules polling, serializes access, handles failure.
- `light.py` — maps lamp state to/from the HA light model.
- `config_flow.py` — discovery + setup, produces a config entry.

## 5. Components

### 5.1 `client.py` — async protocol client (port of `dlight.go`)
Pure `asyncio`, zero external dependencies.

Public API:
```python
class DlightClient:
    def __init__(self, host: str, device_id: str, port: int = 3333,
                 timeout: float = 10.0) -> None: ...
    async def query_info(self) -> DeviceInfo: ...        # model, hw, sw
    async def query_state(self) -> LampState: ...        # on, brightness, kelvin
    async def set_on(self, on: bool) -> None: ...
    async def set_brightness(self, brightness: int) -> None: ...   # 0–100
    async def set_temperature(self, kelvin: int) -> None: ...      # clamped
```

Implementation notes:
- **Connection-per-command** (`asyncio.open_connection` → send → read → close),
  mirroring the proven Go behavior.
- A module-level **`asyncio.Lock`** (per client instance) serializes *all* I/O so
  polls and commands never overlap — respects the one-connection limit.
- Outbound: `writer.write(json.dumps(cmd).encode() + b"\n")`.
- Inbound: `await reader.readexactly(4)` → unpack `>I` → `readexactly(n)`.
- **Generous timeouts** (default 10s) given the slow device; wrap each round-trip
  in `async_timeout`.
- Typed errors: `DlightError` (base), `DlightConnectionError`,
  `DlightProtocolError`, `DlightTimeoutError`. **No process-fatal calls.**
- `on` is serialized explicitly as `true`/`false` (the Go `*bool` quirk): always
  include the key when setting power.

### 5.2 `coordinator.py` — polling strategy (solves problem #2)
`DlightCoordinator(DataUpdateCoordinator[LampState])`:
- `update_interval = timedelta(seconds=<configurable>, default 30)`.
- `_async_setup()` calls `query_info()` once (for device registry metadata).
- `_async_update_data()` calls `query_state()`; on error raises `UpdateFailed`
  (entity → `unavailable`, coordinator backs off and retries).
- After a command, the entity updates `coordinator.data` **optimistically** and
  schedules a **single debounced refresh** (~2s later) rather than an immediate
  poll, to let the lamp settle.
- `always_update=False` (LampState supports `__eq__`) to avoid redundant
  dispatches.

### 5.3 `light.py` — `DlightLight(CoordinatorEntity, LightEntity)`
- `_attr_supported_color_modes = {ColorMode.COLOR_TEMP}`,
  `_attr_color_mode = ColorMode.COLOR_TEMP`.
- `_attr_min_color_temp_kelvin = 2600`, `_attr_max_color_temp_kelvin = 6000`
  (both confirmed empirically — see §3).
- `is_on`, `brightness`, `color_temp_kelvin` derived from `coordinator.data`.
- `async_turn_on(**kwargs)`: read `ATTR_BRIGHTNESS` / `ATTR_COLOR_TEMP_KELVIN`,
  call the matching client setter(s), then optimistic update + debounced refresh.
- `async_turn_off()`: `client.set_on(False)`.
- `DeviceInfo`: `identifiers={(DOMAIN, device_id)}`,
  `connections={(CONNECTION_NETWORK_MAC, mac)}`, `name`, `model` (GLAMP001),
  `sw_version`, `hw_version`, `manufacturer="Google"`.

### 5.4 `config_flow.py`
- **`unique_id` = `device_id`** in *both* flows. The `device_id` is available
  from the zeroconf instance name (`GLAMP_<id>`) and from manual entry, so a lamp
  added manually and later seen via discovery deduplicates correctly. (MAC is only
  available via zeroconf, so it is unsuitable as the shared key; it is still
  recorded as a device-registry *connection* when known.)
- `async_step_zeroconf(discovery_info)`:
  - `host = discovery_info.host`; `device_id` parsed from the instance name
    (`GLAMP_<id>` → `<id>`); `mac` from TXT (kept for the device registry).
  - `await self.async_set_unique_id(device_id)`;
    `self._abort_if_unique_id_configured(updates={CONF_HOST: host})`.
  - Validate by connecting to `host:3333` with `query_info()`; abort
    `cannot_connect` on failure. Then a confirm step.
- `async_step_user(user_input)`: manual `host` + `device_id`; validate via
  `query_info()`; `await self.async_set_unique_id(device_id)` then
  `_abort_if_unique_id_configured()`.
- `OptionsFlow`: poll interval (seconds, default 30, sane min e.g. 5).

### 5.5 `manifest.json`
```json
{
  "domain": "dlight",
  "name": "Google dLight",
  "version": "0.1.0",
  "config_flow": true,
  "iot_class": "local_polling",
  "integration_type": "device",
  "zeroconf": [{ "type": "_ged7._tcp.local.", "name": "glamp*" }],
  "requirements": [],
  "codeowners": ["@thekoma"],
  "documentation": "https://github.com/thekoma/dlight-homeassistant",
  "issue_tracker": "https://github.com/thekoma/dlight-homeassistant/issues"
}
```

### 5.6 `const.py`
`DOMAIN`, `DEFAULT_PORT = 3333`, `DEFAULT_TIMEOUT = 10.0`,
`DEFAULT_SCAN_INTERVAL = 30`, `MIN_KELVIN = 2600`, `MAX_KELVIN = 6000`,
`CONF_DEVICE_ID`, config keys.

## 6. Data model

```python
@dataclass(frozen=True)
class LampState:
    on: bool
    brightness: int      # lamp scale 0–100
    color_temp_kelvin: int

@dataclass(frozen=True)
class DeviceInfo:
    model: str
    hw_version: str
    sw_version: str
```

## 7. Color temperature & brightness mapping

- **Color temp:** HA passes/expects Kelvin (`ATTR_COLOR_TEMP_KELVIN`); the lamp
  speaks Kelvin → **no mireds conversion** (the Go bridge's math is gone). Clamp
  to `[MIN_KELVIN, MAX_KELVIN]` before sending.
- **Brightness:** HA uses 1–255, the lamp 1–100 (observed physical floor 5; the
  minimum keeps the lamp on). Convert with HA's brightness scale helpers
  (`homeassistant.util.scale`) over `1–100`; the lamp floors very low values
  itself. Setting brightness implies power on.

## 8. Error handling & resilience
- All lamp errors surface as `UpdateFailed` (poll) or are caught in command
  handlers and logged; the entity goes `unavailable` rather than crashing HA.
- No `os.Exit` / `log.Fatalf` equivalents anywhere.
- Config-entry setup uses `async_config_entry_first_refresh()` →
  `ConfigEntryNotReady` retry if the lamp is briefly unreachable.

## 9. Packaging & distribution
- `hacs.json` for HACS custom-repository install.
- GitHub Actions: `home-assistant/actions/hassfest`, `hacs/action`, and `pytest`.
- `README.md` with install, discovery, and configuration docs.

## 10. Testing strategy
`pytest` + `pytest-homeassistant-custom-component`:
- **client**: a fake asyncio TCP server implementing the protocol (incl. the
  asymmetric length framing, the slow-response/timeout path, and malformed
  responses).
- **config_flow**: zeroconf happy path, manual happy path, `cannot_connect`,
  `already_configured` (duplicate MAC).
- **light**: turn_on/off, brightness scaling round-trip, color-temp clamping,
  `unavailable` on coordinator failure.
- **coordinator**: serialization (no overlapping I/O), backoff on failure.

## 11. Migration / coexistence
- New integration is independent of the Go bridge; users switch by adding the
  integration and decommissioning the container. No data migration needed.

## 12. Open items to confirm during implementation
- **Color-temperature range**: confirmed **2600K–6000K** via physical extremes
  (§3). Resolved.
- **Brightness**: physical range confirmed **5–100**, minimum stays on (§3).
  Whether the API honors values below the physical floor (1–4) is untested
  (avoided write-testing the live lamp); clamp to `[1, 100]` and rely on the
  lamp's own flooring.
- Exact TXT key casing as delivered by HA's zeroconf (`mac`, `model`, etc. are
  lowercased by HA) — verify in the discovery handler.

## 13. Future (out of scope for v1)
- **Approach B — persistent connection**: reuse one long-lived TCP connection to
  eliminate connect/disconnect churn entirely. Potentially the most lamp-friendly
  option, but unproven with this firmware (idle-socket handling, reconnect, the
  one-connection limit). Revisit if crashes persist under Approach A, possibly as
  a toggle.
- Optional `update`-style exposure of firmware version, multiple lamps already
  supported naturally (one config entry per device).
