frappe.ui.form.on("SaaS sites", "after_save", function (frm) {
  frappe.call({
    method:
      "bettersaas.bettersaas.doctype.saas_sites.saas_sites.updateLimitsOfSite",
    args: {
      max_users: frm.doc.user_limit,
      sitename: frm.doc.site_name,
      max_space: frm.doc.space_limit,
      max_email: frm.doc.email_limit,
      expiry_date: frm.doc.expiry_date,
    },
    callback: function (r) {
      console.log("limits updated", r);
    },
  });
});
// set default values fetched from SaaS settings

// frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_s3
frappe.ui.form.on("SaaS sites", {
  refresh: async function (frm) {
    frm.add_custom_button(__("Login as admin"), async function () {
      // When this button is clicked, do this

      const dec_db_password = (
        await $.ajax({
          url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.getDecryptedPassword",
          type: "GET",
          dataType: "json",
          data: {
            site_name: frm.doc.site_name,
          },
        })
      ).message;
      console.log(dec_db_password);
      let enc_password = CryptoJS.enc.Base64.stringify(
        CryptoJS.enc.Utf8.parse(dec_db_password)
      );
      const query = `?domain=${frm.doc.site_name}&email=Administrator&utm_id=${enc_password}`;

      // do something with these values, like an ajax request
      // or call a server side frappe function using frappe.call
      console.log(query);
      let site_name = frm.doc.site_name;
      if (window.location.port == 8000) {
        site_name += ":8000";
      }
      const urlToRedirect = `http://${site_name}/redirect` + query;
      console.log(urlToRedirect);
      window.open(urlToRedirect, "_blank");
    });
    frm.add_custom_button(__("create backup"), async function () {
      const { resp } = $.ajax({
        url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.take_backup_of_site",
        type: "GET",
        dataType: "json",
        data: {
          sitename: frm.doc.site_name,
        },
      });
      console.log(resp);
    });
    // set limits
    const { message } = await $.ajax({
      url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.getLimitsOfSite",
      type: "GET",
      dataType: "json",
      data: {
        site_name: frm.doc.site_name,
      },
    });
    console.log(message);
    frm.set_value("user_limit", message.users);
    frm.set_value("space_limit", message.space);
    frm.set_value("email_limit", message.emails);
    frm.set_value("plan", message.plan || "Free");
  },
});
