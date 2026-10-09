frappe.ui.form.on("SaaS Remote Command", {
	refresh(frm) {
		if (!["Succeeded", "Superseded"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Retry"), function () {
				frappe.call({
					method: "bettersaas.remote_management.retry_command",
					args: { command_name: frm.doc.name },
					callback: function () {
						frm.reload_doc();
					},
				});
			});
		}
	},
});
