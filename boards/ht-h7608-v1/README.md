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
