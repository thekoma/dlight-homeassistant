# Google dLight — Home Assistant integration

Native Home Assistant integration for the Google **dLight** experimental desk
lamp. Controls power, brightness, and color temperature locally over the lamp's
TCP protocol — no MQTT bridge, no container.

## Install (HACS)
Add this repo as a custom repository (category: Integration), install, restart
Home Assistant. The lamp is auto-discovered via mDNS, or add it manually with its
IP and device ID.
