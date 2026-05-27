# Google dLight — Home Assistant integration

Native Home Assistant integration for the Google **dLight** experimental desk
lamp. Controls power, brightness, and color temperature directly over the lamp's
local TCP protocol — no MQTT bridge, no separate container.

## Features
- Auto-discovery via mDNS (`_ged7._tcp`), plus manual setup (IP + device ID).
- Color temperature (2600–6000K) and brightness.
- Gentle, serialized polling (default 30s, configurable) tuned to avoid
  overloading the lamp, which sustains only one connection at a time.

## Install (HACS)
1. HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/thekoma/dlight-homeassistant`, category **Integration**.
3. Install, restart Home Assistant.
4. The lamp is discovered automatically, or add it via
   Settings → Devices & Services → Add Integration → **Google dLight**.

## Options
Polling interval is configurable under the integration's options.

## Credits
Protocol reverse-engineered from the original `dlight2mqtt` Go bridge by
Philipp Kern. See `docs/specs/` for the design.
