import frappe
from frappe import _
from frappe_s3_attachment.controller import delete_from_cloud
from bettersaas.bettersaas.page.onehash_backups.onehash_backups import schedule_files_backup

def delete_site_files_from_s3(site_name):
    frappe.init(site=site_name)
    frappe.connect()
    files_docs = frappe.db.get_all("File", fields=['*'])
    print(files_docs)
    for doc in files_docs:
        delete_from_cloud(doc, None)
    frappe.destroy()

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
        delete_site_files_from_s3(site_name)
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
        