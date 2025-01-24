import frappe
import os
from frappe.model.document import Document
from frappe.utils import random_string

@frappe.whitelist(allow_guest=True)
def is_stock_site(site):
    stock_site = frappe.db.get_list(
        "SaaS Stock Sites",
		filters={"subdomain": site.split('.')[0]},
		fields=["*"],
        ignore_permissions=True
    )
    return stock_site

def insert_site(site_name, admin_password):
    site = frappe.new_doc("SaaS Stock Sites")
    site.subdomain = site_name
    site.admin_password = admin_password
    site.insert()

def create_multiple_sites_in_parallel(command):
    frappe.utils.execute_in_shell(command)

@frappe.whitelist()
def refresh_stock_sites(*args, **kwargs):
    from frappe.utils.background_jobs import enqueue, get_jobs

    queued_jobs = get_jobs(site=frappe.local.site, queue="long")
    method = "bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.create_multiple_sites_in_parallel"

    config = frappe.get_doc("SaaS Settings")
    domain = frappe.conf.domain
    current_stock = frappe.db.get_list(
        "SaaS Stock Sites", filters={"is_used": "no"}, ignore_permissions=True
    )
    if (method not in queued_jobs[frappe.local.site]) and (len(current_stock) < config.stock_sites_count):
        number_of_sites_to_stock = config.stock_sites_count - len(current_stock)
        for _ in range(number_of_sites_to_stock):
            import string
            import random

            letters = string.ascii_lowercase
            random_string_util = "".join(random.choice(letters) for i in range(10))
            subdomain = random_string_util
            admin_password = random_string(5)
            commands = []
            commands.append(
                "bench new-site {} --install-app erpnext --admin-password {} --db-root-password {}".format(
                    subdomain + "." + domain,
                    admin_password,
                    frappe.conf.root_password,
                )
            )
            commands.append(
                "bench --site {} install-app payments".format(
                    subdomain + "." + domain
                )
            )
            commands.append(
                "bench --site {} install-app frappe_s3_attachment".format(
                    subdomain + "." + domain
                )
            )
            commands.append(
                "bench --site {} install-app whitelabel".format(
                    subdomain + "." + domain
                )
            )
            commands.append(
                "bench --site {} migrate".format(
                    subdomain + "." + domain
                )
            )
            commands.append(
                "bench --site {} install-app clientside".format(
                    subdomain + "." + domain
                )
            )
            admin_subdomain = frappe.conf.admin_subdomain
            commands.append(
                "bench --site {} execute bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.insert_site --args \"'{}','{}'\"".format(
                    admin_subdomain + "." + domain, subdomain, admin_password
                )
            )
            commands = " ; ".join(commands)
            enqueue(
                method,
                queue="long",
                now=True,
                command=commands,
            )

    return "Stock Sites updated"

def delete_stock_sites(doc, method):
    cmd = "bench drop-site {} --db-root-password {} --no-backup".format(
        doc.subdomain + "." + frappe.conf.domain, frappe.conf.root_password
    )
    frappe.utils.execute_in_shell(cmd)

class SaaSStockSites(Document):
    pass
