import frappe
from frappe import _
from bettersaas.bettersaas.page.onehash_backups.onehash_backups import schedule_files_backup

@frappe.whitelist()
def delete_site(site_name):
    doc = frappe.get_list(
        "SaaS Sites", filters={"site_name": site_name}, fields=["site_name", "name"]
    )[0]
    if doc:
        schedule_files_backup(site_name)
        frappe.delete_doc("SaaS Sites", site_name)
        frappe.delete_doc("SaaS Users", site_name)
        frappe.utils.execute_in_shell(
            "bench drop-site {site} --root-password {root_password} --force --no-backup".format(
                site=site_name, root_password=frappe.conf.root_password

            )
        )
        frappe.utils.execute_in_shell(
            "bench setup nginx --yes".format
        )
