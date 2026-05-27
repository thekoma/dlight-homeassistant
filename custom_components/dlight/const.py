"""Constants for the dLight integration."""

DOMAIN = "dlight"

DEFAULT_PORT = 3333
DEFAULT_TIMEOUT = 10.0
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5

MIN_KELVIN = 2600
MAX_KELVIN = 6000

# Lamp brightness scale (HA uses 1-255).
BRIGHTNESS_SCALE = (1, 100)

CONF_DEVICE_ID = "device_id"
CONF_MAC = "mac"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

ZEROCONF_TYPE = "_ged7._tcp.local."
GLAMP_PREFIX = "GLAMP_"
