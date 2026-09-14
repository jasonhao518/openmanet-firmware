# Heltec HT-H7608 V1

This profile targets the original HT-H7608 V1: an MT7628 host with 128 MB RAM,
32 MB SPI flash, and an MM6108 HaLow radio connected over SDIO. Heltec's stock
firmware identifies this hardware as `morse_ekh03v3` and
`Heltec,HT-H7608-V1`; both identifiers are accepted for sysupgrade migration.
The HT-H7608 V1 uses the same RF design and board configuration as HT-HC01 V1:
`bcf_mf08551.bin`. Because the H7608 V1 OTP board-type bits are not programmed,
the first-boot configuration sets this BCF explicitly on the Morse UCI radio;
it does not rely on automatic detection, which would select the non-functional
failsafe BCF.

On first boot both RJ45 switch ports are configured as the `eth0.1` DHCP WAN.
The onboard 2.4 GHz radio creates a downstream `EdgeZ-XXXXXX` AP (using the
final six hex digits of the device MAC) collocated with BATMAN on `br-ahwlan`.
The OpenMANET Mesh Gate address is `10.41.0.1/16`, and DHCP clients use the
`10.41.1.0` range. Both Wi-Fi clients and the HaLow BATMAN mesh can use the
Ethernet uplink when it is connected and supplies DHCP, but the local AP,
LuCI, DHCP, and HaLow mesh remain operational without any upstream connection.
Radio detection is repeated on the clean overlay before these settings are
applied, following the working V1 lite image's initialization path. The old
`OpenMANET-*` management AP is not created.

The HaLow interface uses the EdgeZ defaults (`edgez` / `edgez123`, US channel
27, 1 MHz at 915.5 MHz) with BATMAN_IV and advertises this node as an Internet
gateway. The default 2.4 GHz AP key and root password are both `openmanet`;
change them after login.

The build produces both `*factory.bin` for U-Boot option 0 serial flashing and
`*sysupgrade.bin` for LuCI or `sysupgrade`. The full image includes LuCI, the
OpenMANET interface, MM6108 SDIO driver and firmware, `morse_mesh11sd`, Alfred,
and B.A.T.M.A.N. Advanced. The full image accepts the recovery profile's
`heltec,ht-h7608-v1-lite` identity, so it can be installed directly from the
lite image's LuCI firmware-upgrade page without forcing compatibility.

After the upgrade, connect to the `EdgeZ-XXXXXX` 2.4 GHz AP with password
`openmanet`, then open `http://10.41.0.1/`. Sign in as `root` with password
`openmanet`. The HaLow mesh defaults are SSID/mesh ID `edgez`, SAE key
`edgez123`, US channel 27, and 1 MHz channel width.

When upgrading from the lite image in LuCI, upload the full image's
`*sysupgrade.bin` and clear **Keep settings**. The lite profile assigns
Ethernet to its recovery LAN, while the full OpenMANET profile assigns
Ethernet as its DHCP WAN, so retaining the lite network configuration would
prevent the intended gateway layout from being generated.

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
