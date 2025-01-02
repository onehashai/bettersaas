import frappe
from frappe import _
from bettersaas.bettersaas.page.onehash_backups.onehash_backups import schedule_files_backup

@frappe.whitelist()
def delete_site(site_name):
    saas_sites_doc = frappe.get_list(
        "SaaS Sites", filters={"name": site_name}, fields=["name"]
    )[0]
    saas_users_doc = frappe.get_list(
        "SaaS Users", filters={"name": site_name}, fields=["name"]
    )[0]
    if saas_sites_doc and saas_users_doc:
        schedule_files_backup(site_name)
        frappe.init(site=frappe.conf.admin_url)
        frappe.connect()
        frappe.delete_doc("SaaS Sites", saas_sites_doc.name)
        frappe.delete_doc("SaaS Users", saas_users_doc.name)
        frappe.db.commit()
        frappe.utils.execute_in_shell(
            "bench drop-site {site} --root-password {root_password} --force --no-backup".format(
                site=site_name, root_password=frappe.conf.root_password

            )
        )
        frappe.destroy()
        