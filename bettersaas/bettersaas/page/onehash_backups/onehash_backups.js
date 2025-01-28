frappe.pages['onehash-backups'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Download Backups"),
		single_column: true
	});

	page.add_inner_button(__("Schedule a Backup Now"), function () {
		let d = new frappe.ui.Dialog({
			title: 'Select a Backup Schedule',
			fields: [
				{
					label: 'Frequency',
					fieldtype: 'Select',
					fieldname: 'frequency',
					options: [
						'Daily',
						'Alternate Days',
						'Weekly',
						'Monthly'
					].join('\n')
				},
			],
			size: 'small', 
			primary_action_label: 'Submit',
			primary_action(values) {
				if (values.frequency === "Daily"){
					frappe.call({
						method: "bettersaas.bettersaas.page.onehash_backups.onehash_backups.schedule_files_backup_daily",
					});
				} else if (values.frequency === "Alternate Days"){
					frappe.call({
						method: "bettersaas.bettersaas.page.onehash_backups.onehash_backups.schedule_files_backup_alternate_days",
					});
				} else if (values.frequency === "Weekly"){
					frappe.call({
						method: "bettersaas.bettersaas.page.onehash_backups.onehash_backups.schedule_files_backup_weekly",
					});
				} else if (values.frequency === "Monthly"){
					frappe.call({
						method: "bettersaas.bettersaas.page.onehash_backups.onehash_backups.schedule_files_backup_monthly",
					});
				}    
				d.hide();
			}
		});
		
		d.show();
	});
	
	page.add_inner_button(__("Get Backup Encryption Key"), function () {
		if (frappe.user.has_role("System Manager")) {
			frappe.verify_password(function () {
				frappe.call({
					method: "frappe.utils.backups.get_backup_encryption_key",
					callback: function (r) {
						frappe.msgprint({
							title: __("Backup Encryption Key"),
							message: __(r.message),
							indicator: "blue",
						});
					},
				});
			});
		} else {
			frappe.msgprint({
				title: __("Error"),
				message: __("System Manager privileges required."),
				indicator: "red",
			});
		}
	});

	frappe.breadcrumbs.add("Setup");
	
	$(frappe.render_template("onehash_backups")).appendTo(page.body.addClass("no-border"));
}
