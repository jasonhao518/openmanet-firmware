# Heltec HT-H7608 V1

This profile targets the original HT-H7608 V1: an MT7628 host with 128 MB RAM,
32 MB SPI flash, and an MM6108 HaLow radio connected over SDIO. Heltec's stock
firmware identifies this hardware as `morse_ekh03v3` and
`Heltec,HT-H7608-V1`; both identifiers are accepted for sysupgrade migration.
The runtime identity remains `morse,ekh03v3` so the Morse scripts select the
required `bcf_mf08551.bin` board configuration automatically.

On first boot the Ethernet switch is configured as a DHCP WAN. The onboard
2.4 GHz radio creates a downstream `EdgeZ-XXXXXX` AP (using the final six hex
digits of the device MAC) on `192.168.100.1/24`, and both Wi-Fi clients and the
HaLow BATMAN mesh can use the Ethernet uplink. The old `OpenMANET-*` management
AP is not created.

The HaLow interface uses the EdgeZ defaults (`edgez` / `edgez123`, US channel
27, 1 MHz at 915.5 MHz) with BATMAN_IV and advertises this node as an Internet
gateway. The default 2.4 GHz AP key and root password are both `openmanet`;
change them after login.

The V1 factory layout reserves 0x50000 bytes before firmware and provides
0x1fb0000 bytes (32448 KiB) for the image. Do not install this image on an
HT-H7608 V2; V2 is separate hardware and is intentionally not part of this
profile.

For a small MT7603-only recovery access point, factory image, and reusable
system-image serial flasher, see the
[`ht-h7608-v1-lite` profile](../ht-h7608-v1-lite/README.md).

## Restore the Heltec stock firmware over serial (macOS)

The recovery helper uses U-Boot menu option `0` and OpenKermit's conservative
compatibility mode to restore the pinned Heltec V1 stock image. It verifies the
image size and SHA-256 before opening the serial port, so a V2 image is refused.

Install the one dependency:

```sh
brew install openkermit
```

Connect a 3.3 V TTL adapter (TX to RX, RX to TX, and GND to GND; leave VCC
disconnected), then run:

```sh
./boards/ht-h7608-v1/recover-stock-macos.sh
```

The script detects a single `/dev/cu.usbserial-*` or `/dev/cu.usbmodem*`
adapter. Select one explicitly when multiple adapters are connected:

```sh
./boards/ht-h7608-v1/recover-stock-macos.sh \
  --port /dev/cu.usbserial-BG0107WG
```

After confirming the model, power-cycle the router. The serial transfer at
115200 baud takes about 90 minutes. Do not disconnect power until the script
reports that the stock login prompt was reached.
