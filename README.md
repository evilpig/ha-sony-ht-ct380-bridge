# Sony HT-CT380 Bluetooth Bridge for Home Assistant

An experimental Home Assistant app/add-on that controls a Sony HT-CT380 over its proprietary Bluetooth Classic RFCOMM channel. It exposes volume, subwoofer level, Night Mode, sound mode, input selection, connection status, and recovery controls through MQTT Discovery.

> [!WARNING]
> The HT-CT380 with firmware 2.033 is the only officially supported model. Similar-era Sony soundbars controlled by SongPal or Music Center may use the same protocol, but must be treated as experimental.

## Why this exists

No usable Home Assistant solution could be found for the HT-CT380's Music Center controls. The Android Music Center / SongPal APK was therefore reverse engineered to recover its Sony Tandem RFCOMM service, framing, sequence handling, and control payloads. The implementation then required substantial testing and trial and error on a real soundbar.

This project was developed with assistance from OpenAI ChatGPT and Codex. The hardware testing, observations, safety decisions, and repeated validation were performed interactively by the project owner. It should be considered an experimental community project, not official Sony software.

## What works

- Main volume, 0-50
- Subwoofer level, 0-12
- Night Mode on/off
- Sound modes: ClearAudio+, Standard, Movie, Sports, Game, Music, Portable Audio, and Effect Off
- Inputs: TV, HDMI 1-3, Analog, and BT Audio
- MQTT Discovery entities
- Optional Universal Media Player package
- Read-only control heartbeat
- Bounded automatic recovery and a manual Reconnect Control button
- Optional TV-power-aware recovery and MQTT TV Power status

## Requirements

- Home Assistant OS with a Bluetooth Classic-capable local USB adapter passed through to the VM
- [Home Assistant Bluetooth integration](https://www.home-assistant.io/integrations/bluetooth/)
- [Bluetooth Audio Manager](https://github.com/scyto/ha-bluetooth-audio-manager)
- An MQTT broker such as Mosquitto

An ESPHome Bluetooth proxy is not a substitute: this protocol uses Bluetooth Classic RFCOMM, not BLE.

## Installation

1. In Home Assistant, open **Settings > Apps > App store > Repositories**.
2. Add `https://github.com/evilpig/ha-sony-ht-ct380-bridge`.
3. Install **Sony HT-CT380 Bridge**.
4. Leave the bridge stopped while pairing the soundbar in Bluetooth Audio Manager.
5. Configure your soundbar MAC address and MQTT broker in the bridge options. Optionally set `tv_entity_id` to a reliable TV power entity such as `remote.living_room_tv`.
6. Add the REST commands below, restart Home Assistant, then start the bridge.

Example configuration, replacing the hostname if your Bluetooth Audio Manager installation uses a different slug:

```yaml
rest_command:
  bt_audio_connect:
    url: "http://REPLACE-WITH-BLUETOOTH-AUDIO-MANAGER-HOST:8099/api/connect"
    method: post
    content_type: "application/json"
    payload: '{"address": "AA:BB:CC:DD:EE:FF"}'

  bt_audio_disconnect:
    url: "http://REPLACE-WITH-BLUETOOTH-AUDIO-MANAGER-HOST:8099/api/disconnect"
    method: post
    content_type: "application/json"
    payload: '{"address": "AA:BB:CC:DD:EE:FF"}'
```

If app-hostname DNS does not resolve, use the Home Assistant host IP and the Bluetooth Audio Manager API port instead. Do not use its WebSocket port for these requests.

An optional [Universal Media Player package](home_assistant/sony_ht_ct380_media_player.yaml) combines the discovered entities into one media-player card. Adjust entity IDs if Home Assistant assigned different names.

## Pairing and recovery notes

The HT-CT380 can be temperamental during pairing:

- Stop this bridge before pairing so its RFCOMM listener does not compete with discovery.
- Disconnect Music Center, phones, and nearby computers from the soundbar.
- Manual unpairing and re-pairing in Bluetooth Audio Manager may be necessary.
- If control becomes stale, the bridge performs at most two disconnect/wait/connect recovery cycles and then publishes a diagnostic warning instead of retrying forever.
- The manual **Reconnect Control** button performs the same controlled reset.
- Optional `tv_entity_id` behavior: leave it blank to disable TV awareness. When configured, TV-off suppresses automatic recovery while preserving a healthy control link and manual controls. TV-on waits 15 seconds for HDMI-CEC/audio routing, then refreshes state or requests one serialized, bounded reconnect.

Bluetooth Audio Manager's **Stay Awake** option can help keep the A2DP connection alive, but it does not keep the proprietary Sony control session alive by itself. The bridge independently checks that session using a read-only volume query.

For this soundbar, enable **Stay Awake** in Bluetooth Audio Manager and change its **Reconnect Interval** from the default 30 seconds to **10 seconds**. This does not eliminate Sony control-session timeouts, but it substantially shortens recovery and testing cycles when Bluetooth has to be re-established.

## Protocol and limitations

The soundbar initiates an RFCOMM connection to server channel 11 using UUID `91819D50-5D72-4478-A001-29EB2C763568`. See [docs/PROTOCOL.md](docs/PROTOCOL.md) for verified frames and commands.

The HT-CT380 advertises Sony protocol version 0x3000. Although it acknowledges the newer current-input query, it does not return the expected response, so the bridge retains the last input it actually confirmed. External changes may therefore leave the displayed input stale until the bridge observes or sends another source change.

## Privacy and support

Before sharing logs, remove Bluetooth MAC addresses, local IP addresses, hostnames, MQTT credentials, and Supervisor tokens. Compatibility reports are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

This software is unofficial, experimental, and not affiliated with or endorsed by Sony. Use it at your own risk.

## License

[MIT](LICENSE)
