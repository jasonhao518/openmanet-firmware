include $(TOPDIR)/rules.mk

PKG_NAME:=mt76x8-powersave
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/mt76x8-powersave
  SECTION:=base
  CATEGORY:=Base system
  TITLE:=MT76x8 GPIO and traffic controlled suspend
  DEPENDS:=+kmod-input-gpio-keys +kmod-button-hotplug
endef

define Package/mt76x8-powersave/description
 Enters MT76x8 suspend-to-RAM from GPIO 38 or after a configurable idle
 period. GPIO 11 is configured by the device tree as the wake source.
endef

define Package/mt76x8-powersave/conffiles
/etc/config/mt76x8-powersave
endef

define Build/Compile
endef

define Package/mt76x8-powersave/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/mt76x8-powersave.config $(1)/etc/config/mt76x8-powersave
	$(INSTALL_DIR) $(1)/etc/hotplug.d/button
	$(INSTALL_BIN) ./files/50-mt76x8-powersave $(1)/etc/hotplug.d/button/50-mt76x8-powersave
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/mt76x8-powersave.init $(1)/etc/init.d/mt76x8-powersave
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/mt76x8-powersave.sh $(1)/usr/sbin/mt76x8-powersave
endef

$(eval $(call BuildPackage,mt76x8-powersave))
