frappe.ui.form.on("SaaS Sites", {
  refresh: async function (frm) {
	if (frm.doc.is_enterprise_site) {
		frm.add_custom_button(__("Provision Management"), function () {
			frappe.call({
				method: "bettersaas.remote_management.provision_enterprise_site",
				args: { site_name: frm.doc.site_name },
				freeze: true,
				callback: function () {
					frm.reload_doc();
					frappe.show_alert({ message: __("Provisioned; initial reconciliation queued"), indicator: "green" });
				},
			});
		}, __("Enterprise Management"));
		frm.add_custom_button(__("Reconcile Now"), function () {
			frappe.call({
				method: "bettersaas.remote_management.reconcile_now",
				args: { site_name: frm.doc.site_name },
				callback: function () {
					frm.reload_doc();
					frappe.show_alert({ message: __("Reconciliation queued"), indicator: "blue" });
				},
			});
		}, __("Enterprise Management"));
		frm.add_custom_button(__("Rotate Secret"), function () {
			frappe.confirm(__("Rotate the dedicated management secret for this site?"), function () {
				frappe.call({
					method: "bettersaas.remote_management.rotate_enterprise_secret",
					args: { site_name: frm.doc.site_name },
					freeze: true,
					callback: function () {
						frappe.show_alert({ message: __("Management secret rotated"), indicator: "green" });
					},
				});
			});
		}, __("Enterprise Management"));
	}
	frm.add_custom_button(__('Refresh User Count'), function(){
		frappe.call({
			"method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.get_users_list",
			args: {
				"site_name" : frm.doc.site_name
			},
			async: false,
			callback: function (r) {
				frm.set_value("active_users", (r.message.active_users.length-2));
				frm.set_value("total_users", r.message.total_users.length-2);
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
	
	if (!frm.doc.is_enterprise_site) {
    frm.add_custom_button(__('Delete Site'), function(){
		frappe.confirm(__("This action will delete this saas-site permanently. It cannot be undone. Are you sure ?"), function() {
		frappe.call({
			"method": "bettersaas.api.delete_site",
			args: {
				"site_name" : frm.doc.site_name
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
	}
    if (frm.doc.status == "Active") {
		frm.add_custom_button(__('Disable Site'), function(){
			frappe.confirm(__("This action will disable the site. It can be undone. Are you sure ?"), function() {
				frappe.call({
					"method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.disable_enable_site",
					args: {
						"site_name" : frm.doc.site_name,
						"status": frm.doc.status
					},
					async: false,
					callback: function (r) {
						if (r.message && r.message.unprovisioned) {
							frappe.msgprint(__("Provision enterprise management before disabling this site."));
							return;
						}
						if (frm.doc.is_enterprise_site) {
							frm.reload_doc();
						} else {
							frm.set_value("status", "In-Active");
							frm.save();
						}
						frappe.show_alert({
							message: frm.doc.is_enterprise_site ? __('Site disable queued') : __('Site Disabled Successfully'),
							indicator:'green'
						});
					}
				});
			}, function(){
				frappe.show_alert({
					message: "Cancelled",
					indicator: 'red'
				});
			});
		});
	} 
	else if (frm.doc.status == "In-Active"){
		frm.add_custom_button(__('Enable Site'), function(){
			frappe.confirm(__("This action will enable the site. It can be undone. Are you sure ?"), function() {
				frappe.call({
					"method": "bettersaas.bettersaas.doctype.saas_sites.saas_sites.disable_enable_site",
					args: {
						"site_name" : frm.doc.site_name,
						"status": frm.doc.status
					},
					async: false,
					callback: function (r) {
						if (r.message && r.message.unprovisioned) {
							frappe.msgprint(__("Provision enterprise management before enabling this site."));
							return;
						}
						if (frm.doc.is_enterprise_site) {
							frm.reload_doc();
						} else {
							frm.set_value("status", "Active");
							frm.save();
						}
						frappe.show_alert({
							message: frm.doc.is_enterprise_site ? __('Site enable queued') : __('Site Enabled Successfully'),
							indicator:'green'
						});
					}
				});
			}, function(){
				frappe.show_alert({
					message: "Cancelled",
					indicator: 'red'
				});
			});
		});
	}	

    frm.add_custom_button(__('Login As Administrator'), 
			() => {
			frappe.call('bettersaas.bettersaas.doctype.saas_sites.saas_sites.login', { name: frm.doc.site_name }).then((r)=>{
				if(r.message){
					window.open(`https://${frm.doc.site_name}/app?sid=${r.message}`, '_blank');
				} else{
					console.log(r);
					frappe.msgprint(__("Sorry, Could not login."));
				}
			});
		}
	);

  },
});

frappe.ui.form.on("SaaS Sites", "update_limits", function (frm) {
  frappe.prompt(
    [
      {
        fieldname: "license_limit",
        label: "License Limit",
        fieldtype: "Int",
        default: frm.doc.license_limit,
        reqd: 1,
      },
      {
        fieldname: "storage_limit",
        label: "Storage Limit",
        fieldtype: "Int",
        default: frm.doc.storage_limit.replace("GB", ""),
        description: "Enter in GB ( without the suffix GB )",
        reqd: 1,
      },
      {
        fieldname: "email_limit",
        label: "Email Limit",
        fieldtype: "Int",
        default: frm.doc.email_limit,
        reqd: 1,
      },
    ],
    function (values) {
      frappe.call({
        method:
          "bettersaas.bettersaas.doctype.saas_sites.saas_sites.update_limits",
        args: {
          site_name: frm.doc.site_name,
		  min_license: values.license_limit,
          max_storage: values.storage_limit,
          max_email: values.email_limit,
        },
        callback: function (r) {
		  if (r.message && r.message.unprovisioned) {
			frappe.msgprint(__("Limits were saved as desired state; provision enterprise management to deliver them."));
		  }
        },
      });
    }
  );
});
