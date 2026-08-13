include $(TOPDIR)/rules.mk

PKG_NAME:=wakaama-server
PKG_VERSION:=1.1.0
PKG_RELEASE:=2
PKG_LICENSE:=EPL-2.0 OR BSD-3-Clause
PKG_MAINTAINER:=EdgeZ AI

PKG_PREBUILT:=$(CURDIR)/prebuilt/$(PKG_NAME)_$(PKG_VERSION)-r1_aarch64_cortex-a76.ipk
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)
PKG_FILE_DEPENDS:=$(PKG_PREBUILT)

include $(INCLUDE_DIR)/package.mk

define Package/wakaama-server
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Wakaama LwM2M server with REST API support
  URL:=https://github.com/edgez-ai/wakaama-server
  DEPENDS:=@TARGET_bcm27xx_bcm2712_DEVICE_rpi-5 +libpthread +libavahi-client +libdbus \
	+libuci +libubox +libatomic +libcares +luci-base +luci-compat
endef

define Package/wakaama-server/description
 Prebuilt aarch64_cortex-a76 Wakaama LwM2M server, including its procd
 service, LuCI integration, sensor definitions, and bundled Mosquitto client
 library. This package is limited to the Raspberry Pi 5/BCM2712 target.
endef

define Package/wakaama-server/conffiles
/etc/init.d/lwm2mserver
endef

define Package/wakaama-server/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || /etc/init.d/lwm2mserver enable
endef

define Package/wakaama-server/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/lwm2mserver stop
	/etc/init.d/lwm2mserver disable
}
endef

define Build/Prepare
	rm -rf $(PKG_BUILD_DIR)
	mkdir -p $(PKG_BUILD_DIR)/root
	tar -xzf $(PKG_PREBUILT) -C $(PKG_BUILD_DIR) ./data.tar.gz
	tar -xzf $(PKG_BUILD_DIR)/data.tar.gz -C $(PKG_BUILD_DIR)/root
	# The prebuilt binary has RTSP/GStreamer disabled. Remove obsolete
	# GStreamer debug environment settings from its bundled init script.
	sed -i '/# GStreamer debug settings (hardcoded)./,+3d' $(PKG_BUILD_DIR)/root/etc/init.d/lwm2mserver
	sed -i '/GStreamer debug/d;/GST_DEBUG/d' $(PKG_BUILD_DIR)/root/etc/init.d/lwm2mserver
endef

define Build/Compile
endef

define Package/wakaama-server/install
	$(CP) $(PKG_BUILD_DIR)/root/etc $(1)/
	$(CP) $(PKG_BUILD_DIR)/root/usr $(1)/
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/99-wakaama-server $(1)/etc/uci-defaults/99-wakaama-server
endef

$(eval $(call BuildPackage,wakaama-server))
