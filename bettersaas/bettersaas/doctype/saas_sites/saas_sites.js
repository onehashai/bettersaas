frappe.ui.form.on("SaaS sites", "after_save", function (frm) {
  frappe.call({
    method:
      "bettersaas.bettersaas.doctype.saas_sites.saas_sites.updateLimitsOfSite",
    args: {
      max_users: frm.doc.user_limit,
      sitename: frm.doc.site_name,
      max_space: frm.doc.space_limit,
      max_email: frm.doc.email_limit,
    },
    callback: function (r) {
      console.log("limits updated", r);
    },
  });
});
// set default values fetched from SaaS settings
frappe.ui.form.on("SaaS sites", {
  refresh: function (frm) {
    if (!frm.doc.user_limit) {
      frappe.db
        .get_single_value("SaaS settings", "default_user_limit")
        .then(async (r) => {
          console.log(await frappe.db.get_doc("SaaS settings"));
          frm.set_value("user_limit", r);
        });
    }
    if (!frm.doc.max_email_limit) {
      frappe.db
        .get_single_value("SaaS settings", "default_email_limit")
        .then(async (r) => {
          console.log(await frappe.db.get_doc("SaaS settings"));
          frm.set_value("email_limit", r);
        });
    }
  },
});
