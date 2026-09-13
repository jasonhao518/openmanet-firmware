# Raspberry Pi 5 EdgeZ gateway mode

Current `rpi5-mm8108-usb` images boot directly into this gateway role. This
guide documents the topology, verification steps, and the wizard path needed
to migrate an older installation. In the configuration wizard, gateway mode
is called **Mesh Gate**.

The intended connection is:

```text
Internet / upstream network
           |
    Upstream router (DHCP enabled)
           | LAN port
           | Ethernet
    Raspberry Pi 5 (Mesh Gate)
           | MM8108 USB HaLow mesh
    Other OpenMANET Mesh Points
```

The Pi routes and NATs mesh traffic into the upstream network. Its HaLow
interface remains a mesh interface. Simply changing the wireless mode to
AP, or setting only `network.bat0.gw_mode`, does not configure a complete
OpenMANET gateway.

## 1. Prepare

- Use an upstream router that provides DHCP and already has working internet
  access. Its subnet must not overlap the mesh's `10.41.0.0/16` subnet or the
  downstream Wi-Fi subnet `192.168.100.0/24`.
- Start with one Mesh Gate. Keep the other nodes configured as Mesh Points.
- Record the existing mesh ID, passphrase, country, channel and bandwidth.
  Keep the mesh credentials and compatible radio settings consistent across
  nodes; changing the role does not require changing the mesh credentials.
- Have local HDMI/keyboard access available if possible. Applying the wizard
  can change the management network and disconnect your browser or SSH session.

These instructions use Ethernet as the uplink. Wi-Fi uplink is also offered
by the wizard, but changes the onboard radio's role and access arrangement.

## 2. Connect to the Pi and back up its configuration

On a current first boot, connect to:

| Setting | Initial value |
| --- | --- |
| Downstream Wi-Fi SSID | `EdgeZ-XXXXXX` (MAC-derived) |
| Wi-Fi password | `openmanet` |
| Downstream address | `192.168.100.1` |
| Login user | `root` |
| Initial root password | `openmanet` |

Use your current address and credentials if these have already changed.
Open `http://192.168.100.1` in a browser and sign in. Download a configuration
backup from **System → Backup / Flash Firmware** before proceeding.
Change the public default root and Wi-Fi passwords if you have not already
done so. The initial mesh credentials are `edgez` / `edgez123`;
replace them consistently across all nodes before deployment.

## 3. Migrate an older image with the mesh wizard

Skip this section on a fresh current image; the following settings are already
the first-boot defaults.

1. Open **Wizards → 802.11s Mesh** (the page title is **802.11s Mesh Wizard**).
   If needed, use `http://192.168.100.1/cgi-bin/luci/admin/morse/meshwizard`,
   substituting the Pi's current IP address.
2. For **Mesh Mode**, select **Mesh Gate (Mesh Point with collocated network)**.
3. Under **Setup Mesh Network**, retain the mesh ID, passphrase and operating
   frequency settings used by the other nodes.
4. Under **Upstream Network**, choose **Ethernet**. If several ports are
   listed, select the port connected to the upstream router; the built-in
   Pi Ethernet port is normally `eth0`.
5. For **Traffic Mode**, use **Router**. In the locally inspected wizard this
   is the fixed default; **Router with Firewall** is only offered when
   multiple Ethernet ports are detected. Router mode allows administration
   from the upstream network, so connect it to a trusted router LAN.
6. Keep the ordinary Wi-Fi access point enabled if you want to manage the Pi
   or connect clients through it. Record its SSID and password.
7. Review the final configuration and any IP-change notice, then click
   **Apply**.

Once the configuration is applied, connect the Pi's Ethernet port to a LAN
port on the upstream router if it is not already connected. Allow address
configuration to settle, then reboot using **System → Reboot**, or run
`reboot` from a reconnected SSH or local console session.

## 4. Reconnect after the change

Current images keep the downstream AP at `192.168.100.1`. An older image
reconfigured through the wizard may select another address, so verify the
result shown by the wizard.

Use one of these methods:

- Join the configured Wi-Fi AP again and renew your computer's DHCP lease.
  Check the assigned network settings and the wizard's recorded address.
- Open the upstream router's DHCP lease/client list and find the Pi's
  Ethernet address. With **Router** mode, use that leased IP for the web UI
  or SSH from the upstream LAN.
- At the Pi's local console, run `ip -4 addr` to find its current addresses.

OpenMANET's daemon manages mesh address allocation. Read the actual address
instead of assuming the gateway is always `10.41.1.1`.

## 5. Verify gateway mode and internet access

SSH to the Pi's current address and run:

```sh
uci get mesh11sd.mesh_params.mesh_gate_announcements
uci get network.bat0.gw_mode
batctl meshif bat0 gw_mode
ip -4 addr show br-ahwlan
ip -4 route
```

The first two commands should return `1` and `server`. The live B.A.T.M.A.N.
gateway mode should also report `server`. Confirm a mesh-side address in
`10.41.0.0/16` and a default route through the Ethernet uplink.

Inspect the uplink status:

```sh
ubus call network.interface.wan status
```

Current images configure `eth0` as DHCP interface `wan`. An older installation
migrated with the wizard may instead use logical interface `lan`; inspect both
if its configuration predates this default.

Test connectivity on the gateway:

```sh
ping -c 3 1.1.1.1
nslookup openmanet.net
```

Then run these on another OpenMANET Mesh Point:

```sh
batctl meshif bat0 neighbors
batctl meshif bat0 gateways
ip -4 route
ping -c 3 1.1.1.1
nslookup openmanet.net
```

Look for a reachable mesh neighbor, an advertised gateway, and a usable
default route. Finally test internet access from a client connected to that
Mesh Point. Success on the gateway alone does not prove forwarding works
for the rest of the mesh. ICMP may be filtered on some upstream networks;
also try loading a website from the client.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Lost access after Apply | Rejoin Wi-Fi and renew DHCP, inspect the upstream router's leases, or use `ip -4 addr` at the local console. |
| Gateway has no internet | Check the Ethernet cable, upstream DHCP lease, default route, and upstream router connectivity. |
| No mesh neighbors | Check MM8108 detection and matching mesh credentials, channel and bandwidth. |
| Gateway works, other nodes do not | Check gateway advertisements, the Mesh Point's default route, and firewall forwarding/NAT toward the actual uplink. |
| IP connectivity works but DNS fails | Check `nslookup`, DNS configuration and DHCP-provided DNS on the affected node/client. |

Useful read-only diagnostics:

```sh
logread | grep -Ei 'openmanetd|batman|morse|dnsmasq'
uci show network
uci show firewall
uci show dhcp
```

## Return to Mesh Point mode

Disconnect the upstream Ethernet cable before repurposing that port for mesh
clients. Rerun the **802.11s Mesh Wizard**, select **Mesh Point**, retain the
mesh settings, and use the offered **Bridge** traffic mode for local clients.
Apply, reboot and rediscover the management address. This does not recreate
the Pi 5's separate first-boot management network; restore the saved backup
if you need the exact previous configuration.

## Reference and validation scope

The Pi-specific defaults come from this repository's
[`90-rpi5-remote-access`](../../package/base-files/files/etc/uci-defaults/90-rpi5-remote-access).
Wizard labels and interface behavior were checked against the adjacent local
`packages` checkout's `meshwizard.js` and `tools/morse/{wizard,uci}.js`.
Installed firmware or a different package revision may show different labels.

The upstream [OpenMANET networking guide](https://openmanet.github.io/docs/networking)
also describes routed/NAT gateway operation and rebooting after setup. This
guide was checked against source, but has not been tested on a live Pi 5.
