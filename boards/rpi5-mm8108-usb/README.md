# Raspberry Pi 5 with MM8108 USB

This profile builds OpenMANET for the Raspberry Pi 5 (`bcm2712/rpi-5`) with a
Morse Micro MM8108 connected over USB.

## Reference implementations

- [Morse Micro OpenWrt](https://github.com/MorseMicro/openwrt) is the
  authoritative source for the Morse OpenWrt architecture and MM8108 package
  selection. Its `3.1-dev` branch currently provides an official
  `ekh-bcm2711-mm8108` profile, but no ready-made Raspberry Pi 5/BCM2712
  profile in its OpenWrt `boards/` directory.
- [Morse Micro MM8108 target configuration](https://github.com/MorseMicro/openwrt/blob/3.1-dev/boards/ekh-bcm2711-mm8108/target_diffconfig)
  is used as the reference for MM8108 firmware, board configuration, regulatory
  data, and `netifd-morse` integration.
- [Morse Micro's Raspberry Pi OS build thread](https://community.morsemicro.com/t/build-thread-halow-for-raspberry-pi-os/1124)
  confirms BCM2712/Raspberry Pi 5 kernel support with the Morse 1.16.4 stack.
  It builds the kernel from `bcm2712_defconfig`, enables user access and vendor
  commands in the Morse driver, and states that MM8108 USB does not require a
  device-tree overlay.
- [buildwithparallel/openwrt-morse-rpi5](https://github.com/buildwithparallel/openwrt-morse-rpi5)
  is the working Raspberry Pi 5 integration reference. It identifies itself as
  a community backport and reports the Gateworks MM8108 over USB as working on
  Raspberry Pi 5.
- [Its BCM2712 target configuration](https://github.com/buildwithparallel/openwrt-morse-rpi5/blob/rpi5-mm-23.05/boards/ekh-bcm2712/target_diffconfig)
  is used as the reference for the `rpi-5` image target and 64 MiB boot
  partition.

## Driver compatibility

OpenMANET currently pins the Morse package feed and driver generation already
used by its Raspberry Pi 4 MM8108 USB image. For that generation, the MM8108
USB transport is built with:

```text
CONFIG_PACKAGE_kmod-morse=y
CONFIG_MORSE_USB=y
CONFIG_MORSE_SDIO=n
CONFIG_MORSE_SPI=n
CONFIG_MORSE_USER_ACCESS=y
CONFIG_MORSE_VENDOR_COMMAND=y
```

No Morse device-tree overlay is installed for this profile. USB enumeration
provides device discovery for the MM8108; overlays are required only for buses
such as SPI and SDIO.

The latest official Morse Micro `3.1-dev` SDK also selects `kmod-mm81x` for its
newer MM8108 2.x component stack. That package is not present in OpenMANET's
pinned feeds, so this profile must not select it until the Morse feed and core
components are upgraded together.

## Build

```sh
./scripts/openmanet_setup.sh -i -b rpi5-mm8108-usb
make download -j"$(nproc)"
make -j"$(nproc)" V=sc
```

Images are written to `bin/targets/bcm27xx/bcm2712/`.

The Raspberry Pi 5 image also includes the prebuilt EdgeZ Wakaama LwM2M
server. Its procd service is enabled during image construction and starts as
`lwm2mserver` on boot. The profile explicitly builds Wakaama's c-ares, Avahi,
D-Bus, UCI, libubox, atomic, and LuCI runtime dependencies into the image, so
installing or starting Wakaama does not depend on packages being available from
an external `opkg` feed.

The GitHub Actions build caches downloaded sources, pinned feed repositories,
host tools, the BCM2712 toolchain, compiler objects, and the Pi 5 target's
package/kernel/staging build state. A first build still creates the complete
firmware and uploads a comparatively large cache. Later commits in the same PR
restore that state, let OpenWrt's normal dependency tracking rebuild changed
components, and regenerate the image. Cache statistics are printed at the end
of every build.

## Initial remote access

On first boot, the Raspberry Pi 5 profile enables its onboard (non-HaLow)
Wi-Fi radio as an access point with these temporary development credentials:

```text
SSID: OpenMANET-RPi5
Wi-Fi password: openmanet
SSH user: root
SSH password: openmanet
SSH address: 192.168.12.1
```

The onboard access point uses a dedicated `192.168.12.0/24` management network,
separate from the OpenMANET `10.41.0.0/16` mesh. On first boot, the MM8108 is
also configured as an encrypted 802.11s mesh point and attached to B.A.T.M.A.N.
Advanced using the same topology and address range as the OpenMANET mesh
wizard. The MM8108 uses US channel 27 (1 MHz centered at 915.5 MHz), its
default mesh ID is `edgez`, and its default passphrase is `edgez123`. The mesh
uses BATMAN_IV with gateway mode disabled. Change both Wi-Fi passwords
immediately after connecting. The
defaults are compiled into the public firmware and are not suitable for
deployment.

Interactive Pi 5 logins also reset the terminal to canonical input mode and
normal echo/CR handling. The image enables BusyBox `stty` and automatic window
resize tracking for both HDMI and SSH terminals.
