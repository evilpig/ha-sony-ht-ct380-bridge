# Changelog

## 0.5.18 - 2026-08-16

- Add optional configurable `tv_entity_id` and MQTT TV Power discovery entity
- Suppress automatic recovery while the TV is off without disabling healthy or manual soundbar control
- Refresh Sony state and activation 15 seconds after TV power-on
- Serialize TV, automatic, and manual reconnect requests to prevent overlapping recovery cycles
- Activate a newly established Sony session using an acknowledged unchanged-volume write

## 0.5.16 - 2026-08-16

- Publish subwoofer state only after a successful Sony transport acknowledgement
- Stop treating the constant hexadecimal 0x04 field in the subwoofer query response as its level
- Preserve the last successfully acknowledged subwoofer value in MQTT


## 0.5.15 - 2026-08-16

Initial public release candidate.

- Sony Tandem RFCOMM service and persistent control session
- Volume, subwoofer, Night Mode, sound mode, and input controls
- MQTT Discovery and optional Universal Media Player package
- Alternating Sony sequence handling and alternate-sequence retry
- Read-only control heartbeat
- Bounded Bluetooth disconnect/wait/connect recovery
- Recovery diagnostic and Home Assistant notification
- Sanitized user-configurable MAC and MQTT settings
- AMD64 and AArch64 build metadata
