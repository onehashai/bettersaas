// Copyright (c) 2023, OneHash and contributors
// For license information, please see license.txt

frappe.ui.form.on("SaaS Settings", {
	delete_archived_sites: function(frm) {
		frappe.call({
			method: 'bettersaas.api.delete_archived_sites',
			args: {},
			callback: function(r) {}
		});
	}
});
