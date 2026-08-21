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

## Default access

On first boot, the built-in MT7628 2.4 GHz radio provides a management AP:

| Setting | Default |
| --- | --- |
| Wi-Fi SSID | `openmanet` |
| Wi-Fi security | WPA2-PSK |
| Wi-Fi password | `openmanet` |
| Router address | `192.168.1.1` |
| Username | `root` |
| Login password | `openmanet` |

The access point is attached to the `lan` network. The standard OpenWrt DHCP
server is enabled on that network and leases addresses from
`192.168.1.100` through `192.168.1.249`. The MM8108 HaLow radio is not changed
by these management-Wi-Fi defaults.

Build locally with:

```sh
./scripts/openmanet_setup.sh -i -b mt76x8-mm8108-usb
make -j"$(nproc)" download
make -j"$(nproc)" V=sc
```

## Suspend-to-RAM

GPIO 38 (legacy sysfs number 1038) enters suspend-to-RAM. GPIO 11 (legacy
number 1011) is the active-low wake button. During suspend, Linux suspends
devices, the MT7628 CPU enters WAIT, and the memory controller enables DDR
automatic self-refresh.

Test the wake button before enabling automatic idle suspend:

```sh
/usr/sbin/mt76x8-powersave suspend test
```

If GPIO 11 resumes the board reliably, enable the traffic monitor:

```sh
uci set mt76x8-powersave.main.auto_suspend='1'
uci set mt76x8-powersave.main.idle_seconds='300'
uci commit mt76x8-powersave
/etc/init.d/mt76x8-powersave enable
/etc/init.d/mt76x8-powersave restart
```

`traffic_threshold_bytes` is the maximum aggregate RX/TX change allowed per
poll interval while considering the router idle. Rail-level power removal is
board-dependent; the kernel can only suspend peripherals whose drivers and
power wiring support it.
