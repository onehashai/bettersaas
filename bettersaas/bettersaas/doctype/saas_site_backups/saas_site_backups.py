# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
@frappe.whitelist(allow_guest=True)
def getBackups(site):
    backups = frappe.db.get_list("SaaS site backups",filters={"site":site},fields=["*"],ignore_permissions=True)
    return backups
class SaaSsitebackups(Document):
	pass
