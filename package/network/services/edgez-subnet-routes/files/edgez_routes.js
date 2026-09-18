'use strict';
'require network';

return network.registerProtocol('edgez_routes', {
	getI18n: function() {
		return _('EdgeZ mesh routes');
	},

	getOpkgPackage: function() {
		return 'edgez-subnet-routes';
	},

	isFloating: function() {
		return true;
	},

	isVirtual: function() {
		return true;
	},

	getIfname: function() {
		return this._ubus('l3_device') || 'br-ahwlan';
	},

	getDevices: function() {
		return null;
	},

	containsDevice: function(ifname) {
		return network.getIfnameOf(ifname) === this.getIfname();
	},
});
