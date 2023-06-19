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
    frm.add_custom_button(__("Login as admin"), async function () {
      // When this button is clicked, do this

      var subject = frm.doc.subject;
      var event_type = frm.doc.event_type;
      const dec_db_password = "Rohit123";
      let enc_password = CryptoJS.enc.Base64.stringify(
        CryptoJS.enc.Utf8.parse(dec_db_password)
      );
      const query = `?domain=${frm.doc.site_name}&email=Administrator&password=${enc_password}`;

      // do something with these values, like an ajax request
      // or call a server side frappe function using frappe.call
      console.log(query);
      let site_name = frm.doc.site_name;
      if (window.location.port == 8000) {
        site_name += ":8000";
      }
      const urlToRedirect = `http://${site_name}/redirect` + query;
      console.log(urlToRedirect);
    });
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
