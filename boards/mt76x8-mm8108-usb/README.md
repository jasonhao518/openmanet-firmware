# MT76x8 + MM8108 USB profile

This profile targets a custom MT7628AN router with 256 MiB RAM, 64 MiB
SPI-NOR flash, and a Morse Micro MM8108 USB 2.0 High-Speed dongle connected
to the MT7628 USB host port.

The image assumes this flash layout:

| Offset | Size | Partition |
| --- | --- | --- |
| `0x0000000` | `0x30000` | U-Boot |
| `0x0030000` | `0x10000` | U-Boot environment |
| `0x0040000` | `0x10000` | Factory data |
| `0x0050000` | `0x3fb0000` | Firmware |

Do not flash this image on a board with a different flash size or partition
layout. The board bootloader must initialize the installed RAM and support the
64 MiB SPI-NOR device. The USB connector must operate in host mode and provide
adequate 5 V VBUS power for the dongle.

Build locally with:

```sh
./scripts/openmanet_setup.sh -i -b mt76x8-mm8108-usb
make -j"$(nproc)" download
make -j"$(nproc)" V=sc
```
