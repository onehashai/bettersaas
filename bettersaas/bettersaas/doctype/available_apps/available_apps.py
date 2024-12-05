# Copyright (c) 2024, OneHash and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

@frappe.whitelist(allow_guest=True)
def get_apps():
    all_apps = frappe.db.get_list('Available Apps',fields=['*'],ignore_permissions=True)
    return all_apps

class AvailableApps(Document):
	pass
