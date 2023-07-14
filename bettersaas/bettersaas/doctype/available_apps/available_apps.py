# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cstr
import subprocess
from frappe.model.document import Document

class AvailableApps(Document):
    pass

@frappe.whitelist(allow_guest=True)
def get_apps():
    all_apps = frappe.db.get_list('Available Apps',fields=['*'],ignore_permissions=True)
    return all_apps