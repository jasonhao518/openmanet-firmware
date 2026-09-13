# Heltec HT-H7608 V1 base OpenWrt boot test

This diagnostic profile uses the HT-H7608 V1 device tree and factory flash
layout but contains only the standard OpenWrt base system. Both Wi-Fi radios,
Morse firmware, mesh packages, LuCI, and OpenMANET services are intentionally
absent. It is meant to answer one question: can the board reliably boot and
mount a small OpenWrt image from SPI NOR?

Build it locally with:

```sh
./scripts/openmanet_setup.sh -i
cp boards/ht-h7608-v1-lite/target_diffconfig .config
make defconfig
make -j"$(nproc)"
```

On macOS, use `sysctl -n hw.ncpu` instead of `nproc`.

The GitHub Actions workflow is **Build Base OpenWrt on HT-H7608 V1**. Its
artifact contains the `squashfs-sysupgrade.bin` image plus checksums and build
metadata. The workflow rejects the build if radio/OpenMANET packages leak into
the resolved configuration or if the embedded SquashFS cannot be fully read.

Flash only the `squashfs-sysupgrade.bin` file using U-Boot option `0`, `2`, or
`5`. Do not use bootloader options `7` or `9`. On first boot, use the 115200
8N1 serial console; the standard OpenWrt base image has no initial root
password. Ethernet recovery uses `192.168.1.1`.
