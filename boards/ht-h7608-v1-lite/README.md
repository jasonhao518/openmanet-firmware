# Heltec HT-H7608 V1 Wi-Fi recovery image

This small recovery profile uses the HT-H7608 V1 flash layout and enables only
the MT7628's integrated 2.4 GHz radio. It includes lightweight LuCI for browser
access and firmware upgrades. Morse HaLow, SDIO/MMC, mesh, and OpenMANET
services are deliberately absent.

After first boot, connect using:

- Wi-Fi SSID: `HT-H7608-Recovery`
- Wi-Fi password: `openmanet`
- Router address: `192.168.1.1`
- LuCI: `http://192.168.1.1/`
- SSH user: `root`
- SSH password: `openmanet`

Both exposed Ethernet switch ports are also assigned to the recovery LAN and
serve DHCP. The first boot can take two or three minutes while JFFS2 erases and
initializes the writable overlay. Later boots are faster.

## Build

Build locally on a supported Linux filesystem with:

```sh
# Install only LuCI; do not load the Morse/OpenMANET feeds for this image.
sed -n '/^src-git luci /p' feeds.conf.default > feeds.conf
./scripts/feeds update luci
./scripts/feeds install -p luci -a
cp boards/ht-h7608-v1-lite/target_diffconfig .config
make defconfig
make -j"$(nproc)"
```

The GitHub Actions workflow is **Build Wi-Fi Recovery OpenWrt on HT-H7608
V1**. Its artifact contains:

- `*factory.bin` for U-Boot serial flashing.
- `*sysupgrade.bin` for upgrades from a running compatible OpenWrt system.
- `sha256sums` and build information.

The workflow verifies that the MT7603 Wi-Fi stack and LuCI firmware-upgrade UI
are built in, all Morse packages are absent, the complete SquashFS can be read,
and the factory image fits the V1 firmware partition.

## Flash from macOS

Use only the generated `factory.bin` with the generic serial flashing script:

```sh
./boards/ht-h7608-v1/flash-firmware-macos.sh \
  --firmware "$HOME/Downloads/OPENWRT_FACTORY_IMAGE.bin" \
  --port /dev/cu.usbserial-BG0107WG
```

For an additional checksum guard, copy the matching hash from `sha256sums`:

```sh
./boards/ht-h7608-v1/flash-firmware-macos.sh \
  --firmware "$HOME/Downloads/OPENWRT_FACTORY_IMAGE.bin" \
  --sha256 MATCHING_64_CHARACTER_SHA256 \
  --port /dev/cu.usbserial-BG0107WG
```

The script validates the U-Boot image header and V1 partition-size limit, then
uses U-Boot option `0`. It never selects bootloader options `7` or `9`.

## Upgrade from LuCI

After connecting to the recovery Wi-Fi, open `http://192.168.1.1/` and sign in
as `root` with password `openmanet`. Open **System > Backup / Flash Firmware**
and upload the generated `*sysupgrade.bin` file. Do not upload `factory.bin`
through LuCI; that image is reserved for the U-Boot serial flashing script.

## Factory reset button

With OpenWrt fully booted, press and hold RESET for at least five seconds, then
release it. OpenWrt erases only the JFFS2 configuration overlay and reboots.
The firmware, U-Boot, environment, and factory radio calibration remain
untouched. After reboot, the recovery SSID and credentials above return.

A short press reboots without erasing configuration. Do not interrupt power
while the reset and reboot are in progress.
