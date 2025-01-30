import frappe
from bettersaas.bettersaas.doctype.saas_sites.saas_sites import delete_from_s3
from frappe.utils.password import decrypt
from frappe import _

def delete_site_backups_from_s3(site_name):
    records = frappe.get_list(
        "SaaS Sites Backup",
        filters={"site": site_name},
        fields=["name", "path", "created_on"],
        ignore_permissions=True,
    )
    for i in range(len(records)):
        frappe.delete_doc("SaaS Sites Backup", records[i].name)
        frappe.db.commit()
        delete_from_s3(records[i].path)

def delete_site_files_from_s3(site_name):
    from frappe.frappeclient import FrappeClient
    site = frappe.db.get("SaaS Sites", filters={"site_name": site_name})
    site_password = decrypt(site.encrypted_password, frappe.conf.encryption_key)
    conn = FrappeClient("http://"+site_name, "Administrator", site_password)
    files_docs = conn.get_list("File", fields=['name', 'content_hash'])
    for doc in files_docs:
        if doc['content_hash'] is not None:
            delete_from_s3(doc['content_hash'])

@frappe.whitelist()
def delete_site(site_name):
    saas_sites_doc = frappe.get_list(
        "SaaS Sites", filters={"name": site_name}, fields=["name"]
    )[0]
    saas_users_doc = frappe.get_list(
        "SaaS Users", filters={"name": site_name}, fields=["name"]
    )[0]
    if saas_sites_doc and saas_users_doc:
        delete_site_backups_from_s3(site_name)
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
        
def update_lead_status(email):
    lead_doc = frappe.get_last_doc("Lead",filters={'email_id': email})
    lead_doc.site_status = "Site Created"
    lead_doc.save(ignore_permissions=True)
    frappe.db.commit()