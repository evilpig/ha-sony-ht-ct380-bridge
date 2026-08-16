# Sony Tandem protocol notes

These notes document behavior verified against a Sony HT-CT380 running firmware 2.033. They are not a complete specification.

## Transport

- Bluetooth Classic RFCOMM
- Server channel: `11`
- Service UUID: `91819D50-5D72-4478-A001-29EB2C763568`
- The phone/app side registers a listening RFCOMM profile; the soundbar opens the connection.

The UUID, framing classes, command objects, and sequence rules were recovered from the Sony Music Center / SongPal Android APK and validated against live hardware.

## Frame format

Unescaped frame:

```text
3E
  kind
  sequence
  payload_length (4 bytes, big endian)
  payload
  checksum
3C
```

Bytes 0x3C, 0x3D, and 0x3E are escaped with 0x3D followed by the byte minus 0x10. The checksum is the low byte of the additive sum of kind, sequence, length, and payload. Kind 0x00 carries commands/data; kind 0x01 carries transport acknowledgements. The outgoing sequence alternates between 0 and 1, and Sony acknowledgements supply the next sequence value.

## Verified controls

### Main volume

```text
Query: 91 01
Set:   93 01 02 NN
State: 92 01 NN
Set response: 94 01 NN
```

HT-CT380 range: 0-50.

### Subwoofer

```text
Query: 91 20 03 0F FF 00
Set:   93 20 03 0F FF 01 01 NN
```

HT-CT380 range: 0-12.

### Night Mode

```text
Query: 91 20 01 0F FF 00
Set:   93 20 01 0F FF 01 01 NN
```

NN is 0 for off and 1 for on. A post-set query is required because the immediate set-result packet contains a result code rather than the new state.

### Sound mode

```text
Set: 93 12 HH LL 00 00
```

| Mode | Category |
| --- | --- |
| ClearAudio+ | `0x0FFF` |
| Standard | `0x1FFF` |
| Movie | `0x2FFF` |
| Sports | `0x3FFF` |
| Game | `0x4FFF` |
| Music | `0x5FFF` |
| Portable Audio | `0x6FFF` |
| Effect Off | `0x7FFF` |

### Input

```text
30 INDEX 01 SOURCE_ID NAME_LENGTH NAME
```

| Input | Index | Source ID |
| --- | ---: | ---: |
| TV | 0 | `0x17` |
| HDMI 1 | 1 | `0x18` |
| HDMI 2 | 2 | `0x18` |
| HDMI 3 | 3 | `0x18` |
| Analog | 4 | `0x19` |
| BT Audio | 5 | `0x00` |

The soundbar reports source changes with AppNotify 0x31.

The APK also defines AppGetCurrentInfo `35 ZONE` and AppRetCurrentInfo 0x36, but declares protocol version 0x5000 as its minimum. The HT-CT380 advertises 0x3000, acknowledges the request, and returns no 0x36 payload. The bridge therefore retains the last confirmed source.

## Keepalive and recovery

A read-only volume query every 10 seconds proved to be a reliable control heartbeat. Both the transport acknowledgement and the volume response are required. A missing acknowledgement is retried with the alternate Sony sequence before the session is replaced.

Periodic no-op writes and repeated subwoofer writes were tested and rejected because they were less reliable and unnecessarily changed or occupied the control queue.

## Responsible compatibility testing

Do not assume byte ranges are identical on another model. Start with read-only queries, capture sanitized logs, and verify each setter at safe values. Never publish Bluetooth addresses, network addresses, MQTT credentials, or Supervisor tokens.
