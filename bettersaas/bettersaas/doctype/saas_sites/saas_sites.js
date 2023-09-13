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

	  
    frm.add_custom_button(__('Refresh User Count'), function(){
				frappe.call({
					"method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.get_users_list",
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
							message: "User Count Refreshed !",
							indicator: 'green'
						});
						frm.save();
					}
				})
			});	
	  
    frm.add_custom_button(__('Delete Site'), function(){
          frappe.confirm(__("This action will delete this saas-site permanently. It cannot be undone. Are you sure ?"), function() {
            frappe.call({
              "method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.delete_thesite",
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

    frm.add_custom_button(__('Login As Administrator'), 
			 () => {
				frappe.call('bettersaas.bettersaas.doctype.saas_sites.saas_sites.login', { name: frm.doc.name }).then((r)=>{
					if(r.message){
						window.open(`https://${frm.doc.name}/app?sid=${r.message}`, '_blank');
					} else{
						console.log(r);
						frappe.msgprint(__("Sorry, Could not login."));
					}
				});
			}
		);

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
