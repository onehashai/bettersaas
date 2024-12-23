frappe.pages['onehash-backups'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Download Backups"),
		single_column: true
	});

	page.add_inner_button(__("Set Number of Backups"), function () {
		frappe.set_route("Form", "System Settings");
	  });
	
	page.add_inner_button(__("Schedule a Backup Now"), function () {
		frappe.call({
			method: "bettersaaas.bettersaas.page.onehash_backups.onehash_backups.schedule_files_backup",
		});
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
