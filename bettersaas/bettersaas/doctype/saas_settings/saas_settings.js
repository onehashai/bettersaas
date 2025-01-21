// Copyright (c) 2023, OneHash and contributors
// For license information, please see license.txt

frappe.ui.form.on("SaaS Settings", {
    check_every: function (frm) {
        frappe.call({
            method: "bettersaas.bettersaas.doctype.saas_settings.saas_settings.update_refresh_stock_site_scheduler",
            args: {
                doc_name: frm.doc.name,
                check_every: frm.doc.check_every
            },
            callback: function (r) {
            }
        });
    }
});
