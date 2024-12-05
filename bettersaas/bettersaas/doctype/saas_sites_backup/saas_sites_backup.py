# Copyright (c) 2024, OneHash and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

@frappe.whitelist(allow_guest=True)
def get_backups(site):
    backups = frappe.db.get_list(
        "SaaS Sites Backup",
		filters={"site": site},
		fields=["*"],
        ignore_permissions=True
    )
    return backups

class SaaSSitesBackup(Document):
	pass
