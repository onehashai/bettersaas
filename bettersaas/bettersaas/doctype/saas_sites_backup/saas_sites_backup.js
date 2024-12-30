// Copyright (c) 2024, OneHash and contributors
// For license information, please see license.txt

frappe.ui.form.on("SaaS Sites Backup", {
	refresh(frm) {
        frm.add_custom_button(__("Restore Site"), async function () {
            await $.ajax({
              url: "/api/method/bettersaas.bettersaas.doctype.saas_sites_backup.saas_sites_backup.restore_site",
              type: "GET",
              dataType: "json",
              data: {
                backup_id: frm.doc.name,
                site_name: frm.doc.site,
                encrypted: frm.doc.encrypted,
              },
            });
            frappe.realtime.on("site_restored", function (data) {
                frappe.msgprint("Site Restored Successfully", data);
            });
        });
	},
});
