import frappe

@frappe.whitelist()
def schedule_files_backup():
    frappe.msgprint("This page is not available in this version of OneHash CRM. Please visit OneHash Backups page")