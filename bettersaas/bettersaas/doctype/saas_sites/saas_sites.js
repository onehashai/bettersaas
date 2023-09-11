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
    frm.add_custom_button(__('Delete Site'), function(){
	   //  frappe.warn(
    //   "Are you sure you want to proceed?",
    //   " This action is not reversible.",
    //   () => {
    //     // action to perform if Continue is selected
    //     frappe.call({
    //       method: "clientside.clientside.utils.delete_site_from_server",

    //       freeze_message: __("Deleting site"),
    //       freeze: true,
    //       error: function () {
    //         frappe.msgprint("Site has been deleted successfully");
    //         // refresh page
    //         window.location.reload();
    //       },
    //     });
    //   },
    //   "Continue",
    //   true
    // );
          frappe.confirm(__("This action will delete this saas-site permanently. It cannot be undone. Are you sure ?"), function() {
            frappe.call({
              "method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.delete_site",
              args: {
                "site_name" : frm.doc.name
              },
              async: false,
              callback: function (r) {
               
              }
            });
          }, function(){
            frappe.show_alert({
              message: "Cancelled !!",
              indicator: 'red'
            });
          });
          
        });
    if (frm.doc.site_status == "Active") {
				frm.add_custom_button(__('Disable Site'), function(){
					frappe.confirm(__("This action will disable the site. It can be undone. Are you sure ?"), function() {
						frappe.call({
							"method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.disable_enable_site",
							args: {
								"site_name" : frm.doc.name,
								"status": frm.doc.site_status
							},
							async: false,
							callback: function (r) {
								frm.set_value("site_status", "In-Active");
								frm.save();
								frappe.msgprint("Site Disabled Sucessfully !!!");
							}
						});
					}, function(){
						frappe.show_alert({
							message: "Cancelled !!",
							indicator: 'red'
						});
					});
				});
			} 
			else if (frm.doc.site_status == "In-Active"){
				frm.add_custom_button(__('Enable Site'), function(){
					frappe.confirm(__("This action will enable the site. It can be undone. Are you sure ?"), function() {
						frappe.call({
							"method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.disable_enable_site",
							args: {
								"site_name" : frm.doc.name,
								"status": frm.doc.site_status
							},
							async: false,
							callback: function (r) {
								frm.set_value("site_status", "Active");
								frm.save();
								frappe.msgprint("Site Enabled Sucessfully !!!");
							}
						});
					}, function(){
						frappe.show_alert({
							message: "Cancelled !!",
							indicator: 'red'
						});
					});
				});
			}	
    frm.add_custom_button(__("Login As Administrator"), async function () {
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
	    //-------------------------------------------------------------------------------------------------------
        let site_name = frm.doc.site_name;
	const loginurl = `https://${site_name}/api/method/login?usr=Administrator&pwd=${dec_db_password}`;
	const mainsite = `https://${site_name}/app`;
	const loginWindow = window.open(loginurl, "_blank");
	
	setTimeout(() => {
	    loginWindow.close();
	    window.open(mainsite, "_blank");
	}, 1500);
	    //------------------------------------------------------------------------------------------------------
      // let enc_password = CryptoJS.enc.Base64.stringify(
      //   CryptoJS.enc.Utf8.parse(dec_db_password)
      // );
      // const query = `?domain=${frm.doc.site_name}&email=Administrator&utm_id=${enc_password}`;

      // // do something with these values, like an ajax request
      // // or call a server side frappe function using frappe.call
      // console.log(query);
      // let site_name = frm.doc.site_name;
      // if (window.location.port == 8000) {
      //   site_name += ":8000";
      // }
      // const urlToRedirect = `http://${site_name}/redirect` + query;
      // console.log(urlToRedirect);
      // window.open(urlToRedirect, "_blank");
    });
    frm.add_custom_button(__("Create Backup"), async function () {
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
