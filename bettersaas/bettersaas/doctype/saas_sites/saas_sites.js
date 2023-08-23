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

// frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_s3
frappe.ui.form.on("SaaS sites", {
  refresh: async function (frm) {
		frm.refresh_field("user_details");
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Refresh User Count'), function(){
				frappe.call({
					"method": "bettersaas.bettersaas.doctype.saas_users.saas_users.get_users_list",
					args: {
						"site_name" : frm.doc.name
					},
					async: false,
					callback: function (r) {
						frm.set_value("number_of_users", r.message.total_users.length-2);
						frm.set_value("number_of_active_users", (r.message.active_users.length-2));
						frm.clear_table("user_details");
						for (let i = 0; i < r.message.total_users.length; i++) {
							const element = r.message.total_users[i];
							if(element.name=="Administrator" || element.name=="Guest"){
								continue;
							}
							let row = frappe.model.add_child(frm.doc, "User Details", "user_details");
							row.email_id = element.name;
							row.first_name = element.first_name;
							row.last_name = element.last_name;
							row.active = element.enabled;
							row.user_type = element.user_type;
							row.last_active = element.last_active;
						}
						frm.refresh_fields("user_details");
						frappe.show_alert({
							message: "User Count Refreshed !!",
							indicator: 'green'
						});
						frm.save();
					}
				})
			});
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
  },
});

frappe.ui.form.on("SaaS sites", "update_limits", function (frm) {
  // create a frappe ui dialog with email limit, space limit, user limit, expiry date
  frappe.prompt(
    [
      {
        fieldname: "email_limit",
        label: "Email Limit",
        fieldtype: "Int",
        default: frm.doc.email_limit,
        reqd: 1,
      },
      {
        fieldname: "space_limit",
        label: "Space Limit",
        fieldtype: "Int",
        default: frm.doc.space_limit.replace("GB", ""),
        description: "Enter in GB ( without the suffix GB )",
        reqd: 1,
      },
      {
        fieldname: "user_limit",
        label: "User Limit",
        fieldtype: "Int",
        default: frm.doc.user_limit == "Unlimited" ? -1 : frm.doc.user_limit,
        reqd: 1,
        description: "Enter -1 for unlimited users",
      },
    ],
    function (values) {
      frappe.call({
        method:
          "bettersaas.bettersaas.doctype.saas_sites.saas_sites.updateLimitsOfSite",
        args: {
          max_users:
            values.user_limit == -1 || values.user_limit == "-1"
              ? 1000000
              : values.user_limit,
          sitename: frm.doc.site_name,
          max_space: values.space_limit,
          max_email: values.email_limit,
          expiry_date: values.expiry_date,
        },
        callback: function (r) {
          console.log("limits updated", r);
        },
      });
    }
  );
});
