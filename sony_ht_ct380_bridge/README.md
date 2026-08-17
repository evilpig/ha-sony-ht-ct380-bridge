# Sony HT-CT380 Bridge

Experimental Home Assistant app/add-on for the proprietary Sony Tandem Bluetooth Classic control channel used by the HT-CT380.

## Tested support

Only the Sony HT-CT380 with firmware 2.033 is officially tested. Similar SongPal / Music Center devices may use related commands but are unsupported until validated on hardware.

## Before starting

1. Install the official Home Assistant Bluetooth integration.
2. Install Bluetooth Audio Manager.
3. Pass a Bluetooth Classic-capable local adapter to HAOS.
4. Stop this bridge while pairing.
5. Pair and connect the soundbar in Bluetooth Audio Manager.
6. Configure the soundbar MAC and MQTT broker in this app.
7. Add the required `rest_command.bt_audio_connect` and `rest_command.bt_audio_disconnect` services described in the repository README.
8. Start the bridge.

## Pairing warning

The soundbar can be temperamental. Manual unpairing and re-pairing through Bluetooth Audio Manager may be necessary. Keep phones and computers disconnected while establishing the Home Assistant pairing.

## Runtime

The bridge publishes MQTT Discovery entities for volume, subwoofer, Night Mode, sound mode, inputs, control status, recovery, and manual reconnect. A read-only status heartbeat runs every 10 seconds. Recovery is bounded and stops with a warning after two failed cycles.

For the tested HT-CT380 setup, enable Bluetooth Audio Manager **Stay Awake** and set **Reconnect Interval** to **10 seconds** instead of 30 seconds to reduce recovery delays.

See the [full repository documentation](https://github.com/evilpig/ha-sony-ht-ct380-bridge) for installation, troubleshooting, protocol details, the AI-assisted reverse-engineering disclosure, and the optional media player package.
