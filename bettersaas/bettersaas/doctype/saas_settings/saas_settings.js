// Copyright (c) 2023, OneHash and contributors
// For license information, please see license.txt

frappe.ui.form.on("SaaS settings", {
	delete_archived_sites: function(frm) {
		frappe.call({
			method: 'bettersaas.api.delarchived',
			args: {},
			callback: function(r) {}
		});
	}
});
