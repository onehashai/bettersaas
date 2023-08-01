import frappe

domain = frappe.conf.get("domain")
from frappe.model.document import Document
import os

log = open("some file.txt", "a")
from frappe.utils import random_string
from frappe.utils import nowdate, nowtime


def getSiteConfig():
    siteConfig = frappe.get_doc("SaaS settings")
    return siteConfig


def insertSite(site_name, admin_password):
    site = frappe.new_doc("SaaS stock sites")
    site.subdomain = site_name
    site.admin_password = admin_password
    site.insert()


def create_multiple_sites_in_parallel(command, db_values):
    print("creating multiple sites in parallel")
    frappe.utils.execute_in_shell(command)


def deleteSite(sitename):
    from subprocess import Popen

    config = getSiteConfig()
    command = "bench drop-site {} --force --no-backup --db-root-password {}".format(
        sitename, config.db_password
    )
    process = Popen(command, shell=True, stdout=log)
    process.wait()
    if domain != "localhost":
        os.system(
            "echo {} | sudo -S sudo service nginx reload".format(config.root_password)
        )
    print(process.returncode)


@frappe.whitelist()
def deleteUsedSites():
    sites = frappe.db.get_list("SaaS stock sites", filters={"isUsed": "yes"})
    for site in sites:
        deleteSite(site.subdomain + "." + domain)
    frappe.db.delete("SaaS stock sites", filters={"isUsed": "yes"})
    return "Deleted test sites"


@frappe.whitelist()
def check_stock_sites():
    config = frappe.get_doc("SaaS settings")
    if not config.ssc_enabled:
        return
    if not config.run_at_interval1:
        return
    curtime = nowtime()
    if curtime[:2] == "00":
        curtime = "24" + curtime[2:]

    if int(curtime[:2]) % int(config.run_at_interval1) != 0:
        return

    refreshStockSites()


@frappe.whitelist()
def refreshStockSites(*args, **kwargs):
    print("refreshing stock sites")
    config = getSiteConfig()
    commands = []
    currentStock = frappe.db.get_list(
        "SaaS stock sites", filters={"is_used": "no"}, ignore_permissions=True
    )
    print("In stock", len(currentStock))
    db_values = []
    if len(currentStock) < int(config.stock_site_count):
        number_of_sites_to_stock = int(config.stock_site_count) - len(currentStock)
        for _ in range(number_of_sites_to_stock):
            import string
            import random

            letters = string.ascii_lowercase
            random_string_util = "".join(random.choice(letters) for i in range(10))
            subdomain = random_string_util
            adminPassword = random_string(5)
            config.db_password = config.get_password("db_password")
            this_command = []
            this_command.append(
                "bench new-site {} --install-app erpnext  --admin-password {} --db-root-password {}".format(
                    subdomain + "." + domain,
                    adminPassword,
                    config.get_password("db_password"),
                )
            )

            apps_to_install = [
                frappe.get_doc("Available Apps", x.as_dict().app).app_name
                for x in frappe.get_doc("SaaS settings").apps_to_install
            ]
            print(apps_to_install)
            for app in apps_to_install:
                this_command.append(
                    "bench --site {} install-app {}".format(
                        subdomain + "." + domain, app.strip()
                    )
                )

            this_command.append(
                "bench --site {} install-app clientside".format(
                    subdomain + "." + domain
                )
            )
            adminSubdomain = frappe.conf.get("admin_subdomain")
            this_command.append(
                "bench --site {} execute bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.insertSite --args \"'{}','{}'\"".format(
                    adminSubdomain + "." + domain, subdomain, adminPassword
                )
            )
            site_defaults = frappe.get_doc("SaaS settings")
            this_command.append(
                "bench --site {} set-config max_users {}".format(
                    subdomain + "." + domain, site_defaults.default_user_limit
                )
            )
            this_command.append(
                "bench --site {} set-config max_email {}".format(
                    subdomain + "." + domain, site_defaults.default_email_limit
                )
            )
            this_command = " ; ".join(this_command)
            print("adding to queue,", this_command)
            method = "bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.create_multiple_sites_in_parallel"
            db_values.append([subdomain, adminPassword])
            frappe.enqueue(
                method,
                command=this_command,
                db_values=db_values,
                queue="short",
                now=True,
            )

    return "Database will be updated soon with stock sites "


class SaaSstocksites(Document):
    pass
