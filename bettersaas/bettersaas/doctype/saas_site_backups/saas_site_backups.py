# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from clientside.clientside.utils import take_backups_s3

@frappe.whitelist(allow_guest=True)
def getBackups(site):
    backups = frappe.db.get_list("SaaS site backups",filters={"site":site,"created_by_user":1},fields=["*"],ignore_permissions=True)
    return backups

@frappe.whitelist(allow_guest=True)
def generateOneHashBackups():
    sites = frappe.get_list('SaaS sites', fields=['site_name'])
    config = frappe.get_doc("SaaS settings")
    for site in sites:
        frappe.enqueue("bettersaas.bettersaas.doctype.saas_site_backups.saas_site_backups.backup_to_s3_helper",is_manual=1,backup_limit=config.backup_limit,site=site["site_name"],now=1)
def backup_to_s3_helper(is_manual,backup_limit,site):
    print(is_manual,backup_limit,site)
    take_backups_s3(is_manual=is_manual,backup_limit=backup_limit,site=site)
class SaaSsitebackups(Document):
	pass
