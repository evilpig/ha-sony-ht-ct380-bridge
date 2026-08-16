# Contributing

Compatibility reports and protocol corrections are welcome.

Please include:

- Sony model and firmware
- Home Assistant installation type and version
- Bluetooth adapter chipset
- Whether SongPal or Music Center controls the device
- Sanitized bridge logs around one deliberate command
- Exact expected and observed behavior

Remove Bluetooth MAC addresses, local IP addresses, hostnames, usernames, MQTT credentials, and tokens before posting.

The HT-CT380 is the only officially supported device. Changes for other models should preserve HT-CT380 behavior and identify model-specific payloads explicitly.

Run this syntax check before submitting Python changes:

```bash
python3 -m py_compile sony_ht_ct380_bridge/bridge.py
```
