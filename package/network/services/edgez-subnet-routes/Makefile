include $(TOPDIR)/rules.mk

PKG_NAME:=edgez-subnet-routes
PKG_RELEASE:=4
PKG_LICENSE:=MIT

include $(INCLUDE_DIR)/package.mk

define Package/edgez-subnet-routes
  SECTION:=net
  CATEGORY:=Network
  TITLE:=EdgeZ Alfred IPv4 routes via netifd
  DEPENDS:=+alfred +python3 +ip-full +netifd +ubus
endef

define Build/Compile
endef

define Package/edgez-subnet-routes/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/lib/netifd/proto $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/edgez-subnet-routes.py $(1)/usr/sbin/edgez-subnet-routes
	$(INSTALL_BIN) ./files/edgez_routes.sh $(1)/lib/netifd/proto/edgez_routes.sh
	$(INSTALL_BIN) ./files/99-edgez-routes $(1)/etc/uci-defaults/99-edgez-routes
endef

$(eval $(call BuildPackage,edgez-subnet-routes))
