# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.core.doctype.user.user import test_password_strength
from bettersaas.bettersaas.doctype.saas_users.saas_users import create_user
import subprocess as sp
import os
from frappe.utils.password import decrypt, encrypt
from frappe.model.document import Document
import re


@frappe.whitelist(allow_guest=True)
def markSiteAsUsed(site):
    doc = frappe.get_doc("SaaS stock sites", filters={"subdomain": site})
    doc.is_used = "yes"
    doc.save(ignore_permissions=True)


def executeCommands(commands):
    config = frappe.get_doc("SaaS settings")
    command = " ; ".join(commands)
    print("executing ", command)
    process = sp.Popen(command, shell=True)
    process.wait()
    if frappe.conf.domain != "localhost":
        os.system(
            "echo {} | sudo -S sudo service nginx reload".format(config.root_password)
        )


@frappe.whitelist(allow_guest=True)
def check_subdomain():
    restricted_subdomains = frappe.get_doc("SaaS settings").restricted_subdomains.split(
        ","
    )
    site = frappe.get_all(
        "SaaS sites",
        filters={
            "site_name": frappe.form_dict.get("subdomain") + "." + frappe.conf.domain
        },
    )
    print(site)
    if len(site) > 0:
        return {"status": "failed"}
    subdomain = frappe.form_dict.get("subdomain")
    if subdomain in restricted_subdomains:
        return {"status": "failed"}
    else:
        return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def check_password_strength(*args, **kwargs):
    passphrase = kwargs["password"]
    first_name = kwargs["first_name"]
    last_name = kwargs["last_name"]
    email = kwargs["email"]
    print(passphrase, first_name, last_name, email)
    user_data = (first_name, "", last_name, email, "")
    if "'" in passphrase or '"' in passphrase:
        return {
            "feedback": {
                "password_policy_validation_passed": False,
                "suggestions": ["Password should not contain ' or \""],
            }
        }
    return test_password_strength(passphrase, user_data=user_data)


@frappe.whitelist()
def checkEmailFormatWithRegex(email):
    regex = "^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w+$"
    if re.search(regex, email):
        return True
    else:
        return False


@frappe.whitelist(allow_guest=True)
def setupSite(*args, **kwargs):
    print(kwargs)
    doc = json.loads(kwargs["doc"])
    company_name = doc["company_name"]
    subdomain = doc["subdomain"]
    admin_password = doc["password"]
    fname = doc["first_name"]
    lname = doc["last_name"]
    email = doc["email"]
    config = frappe.get_doc("SaaS settings")
    if not subdomain:
        return "SUBDOMAIN_NOT_PROVIDED"
    if not admin_password:
        return "ADMIN_PASSWORD_NOT_PROVIDED"
    if not fname:
        return "FIRST_NAME_NOT_PROVIDED"
    if not lname:
        return "LAST_NAME_NOT_PROVIDED"
    if checkEmailFormatWithRegex(email) == False:
        return "EMAIL_NOT_PROVIDED"
    if not company_name:
        return "COMPANY_NAME_NOT_PROVIDED"
    if (
        check_password_strength(
            password=admin_password, first_name=fname, last_name=lname, email=email
        )["feedback"]["password_policy_validation_passed"]
        == False
    ):
        return "PASSWORD_NOT_STRONG"
    new_site = subdomain + "." + frappe.conf.domain
    create_user(
        first_name=fname,
        last_name=lname,
        email=email,
        site=subdomain + "." + frappe.conf.domain,
        phone=doc["phone"],
    )
    stock_sites = frappe.db.get_list(
        "SaaS stock sites", filters={"is_used": "no"}, ignore_permissions=True
    )
    target_site = None
    commands = []
    print(len(stock_sites))
    if len(stock_sites) == 0:
        commands.append(
            "bench new-site {} --install-app erpnext  --admin-password {} --db-root-password {}".format(
                new_site, admin_password, config.db_password
            )
        )
        commands.append("bench --site {} install-app clientside".format(new_site))
        commands.append("bench --site {} install-app whitelabel".format(new_site))
        site = frappe.new_doc("SaaS stock sites")
        site.subdomain = subdomain
        site.admin_password = admin_password
        site.insert(ignore_permissions=True)
        target_site = site
    else:
        target_site = frappe.get_doc(
            "SaaS stock sites", stock_sites[0]["name"], ignore_permissions=True
        )
    print("using ", target_site.subdomain, "to create ", subdomain)

    commands.append(
        "bench --site {} set-admin-password {}".format(
            target_site.subdomain + "." + frappe.conf.domain, admin_password
        )
    )
    commands.append(
        "bench setup add-domain {} --site {} ".format(
            new_site, target_site.subdomain + "." + frappe.conf.domain
        )
    )
    commands.append(
        "cd /home/frappe/frappe-bench/sites & mv {}.{} {}".format(
            target_site.subdomain, frappe.conf.domain, new_site
        )
    )
    site_defaults = frappe.get_doc("SaaS settings")
    commands.append(
        "bench --site {} set-config max_users {}".format(
            new_site, site_defaults.default_user_limit
        )
    )
    commands.append(
        "bench --site {} set-config max_email {}".format(
            new_site, site_defaults.default_email_limit
        )
    )
    commands.append(
        "bench --site {} set-config max_space {}".format(
            new_site, site_defaults.default_space_limit
        )
    )
    commands.append(
        "bench --site {} set-config site_name {}".format(new_site, new_site)
    )
    expiry_days = int(config.expiry_days)
    expiry_date = frappe.utils.add_days(frappe.utils.nowdate(), expiry_days)
    commands.append(
        "bench --site {} set-config expiry_date {}".format(new_site, expiry_date)
    )
    commands.append(
        "bench --site {} set-config space {}".format(new_site, expiry_date)
    )
    commands.append(
        "bench --site {} set-config creation_date {}".format(new_site, frappe.utils.nowdate())
    )
    commands.append("bench --site {} set-maintenance-mode off".format(new_site))
    commands.append(
        "bench --site {} execute bettersaas.bettersaas.doctype.saas_sites.saas_sites.markSiteAsUsed --args \"'{}'\"".format(
            subdomain + "." + frappe.conf.domain, subdomain
        )
    )
    target_site.is_used = "yes"
    target_site.save(ignore_permissions=True)
    commands.append("bench setup nginx --yes")
    executeCommands(commands)
    new_site_doc = frappe.new_doc("SaaS sites")
    enc_key = encrypt(admin_password, frappe.conf.enc_key)
    print(enc_key)
    new_site_doc.encrypted_password = enc_key
    new_site_doc.linked_email = email
    new_site_doc.site_name = new_site
    new_site_doc.expiry_date = expiry_date
    new_site_doc.save(ignore_permissions=True)
    print("creating the first user")
    sub = subdomain
    if frappe.conf.subdomain == "localhost":
        sub = target_site.subdomain
    return {"subdomain": sub, "enc_password": enc_key}


@frappe.whitelist(allow_guest=True)
def checkSiteCreated(*args, **kwargs):
    doc = json.loads(kwargs["doc"])
    sitename = doc["site_name"]
    site = frappe.db.get_list(
        "SaaS sites",
        filters={"site_name": sitename + "." + frappe.conf.domain},
        ignore_permissions=True,
    )
    print(site)
    if len(site) > 0:
        return "yes"
    else:
        return "no"


@frappe.whitelist()
def updateLimitsOfSite(*args, **kwargs):
    print("updaing limits", kwargs)
    commands = []
    for key, value in kwargs.items():
        if key in ["max_users", "max_email", "max_space","expiry_date"]:
            commands.append(
                "bench --site   {} set-config {} {}".format(
                    kwargs["sitename"], key, value
                )
            )
    os.system(" & ".join(commands))


@frappe.whitelist()
def getDecryptedPassword(*args, **kwargs):
    print(kwargs)
    site = frappe.db.get("SaaS sites", filters={"site_name": kwargs["site_name"]})
    print(site, frappe.conf.enc_key)
    return decrypt(site.encrypted_password, frappe.conf.enc_key)


@frappe.whitelist()
def take_backup_of_site(sitename):
    print("take_backup_of_site", sitename)
    command = (
        "bench --site {} execute clientside.clientside.utils.take_backups_s3".format(
            sitename
        )
    )
    frappe.utils.execute_in_shell(command)
    return "executing command: " + command


def insert_backup_record(file_name, key, site):
    import datetime

    doc = frappe.get_doc("SaaS site backups")
    doc.site_name = site
    doc.file_name = file_name
    doc.created_on = datetime.datetime.now()
    doc.key = key
    doc.save(ignore_permissions=True)

@frappe.whitelist(allow_guest=True)
def delete_site(*args, **kwargs):
    print("DELETING SITE", kwargs)
    doc = frappe.get_doc("SaaS sites", {"site_name": kwargs["site_name"]})
    doc.site_deleted  = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "done"
class SaaSsites(Document):
    pass
