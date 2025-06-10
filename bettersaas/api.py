import frappe
import jwt, uuid, time
from bettersaas.bettersaas.doctype.saas_sites.saas_sites import delete_from_s3
from frappe.utils.password import decrypt
from frappe import _

def bettersaas_patch():
    onehash_workspaces = frappe.get_all(
		"Workspace",
		filters={"name": ("in", ["OneHash Integrations", "OneHash Settings"])},
		fields=["name", "title", "icon", "indicator_color", "parent_page as parent", "public"],
	)

    erpnext_workspaces = frappe.get_all(
		"Workspace",
		filters={"name": ("in", ["ERPNext Integrations", "ERPNext Settings"])},
		fields=["name", "title", "icon", "indicator_color", "parent_page as parent", "public"],
	)

    if onehash_workspaces and erpnext_workspaces:
        for workspace in erpnext_workspaces:
            frappe.delete_doc("Workspace", workspace["name"], force=True)
            frappe.db.commit()
    
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

def generate_jwt_token(user):
    from frappe.utils.password import get_decrypted_password
    
    user_details = frappe.get_doc("User", user)
    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        api_secret = frappe.generate_hash(length=15)
        user_details.api_key = api_key
        user_details.api_secret = api_secret
        user_details.save()
        frappe.db.commit()

    doctype = "User"
    doc = frappe.db.get_value(doctype=doctype, filters={"api_key": user_details.api_key}, fieldname=["name"])
    if not doc:
        raise frappe.AuthenticationError
    user_details.api_secret = get_decrypted_password(doctype, doc, fieldname="api_secret")
    timezone = user_details.time_zone or frappe.defaults.get_global_default("time_zone") or "UTC"

    payload = {
        "api_key": user_details.api_key,
        "api_secret": user_details.api_secret,
        "iat": int(time.time()),
        "jti": str(uuid.uuid4()),
        "iss": frappe.conf.domain,
        "tz": timezone,
    }
    secret_key = frappe.conf.copilot_secret_key
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

@frappe.whitelist()
def get_jwt_token():
    user = frappe.session.user
    token = generate_jwt_token(user)
    return {"token": token}