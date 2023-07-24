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
from clientside.stripe import StripeSubscriptionManager
from bettersaas.bettersaas.api import upgrade_site
@frappe.whitelist(allow_guest=True)
def markSiteAsUsed(site):
    print(site)
    doc = frappe.get_last_doc("SaaS stock sites", filters={"subdomain": site})
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
    company_name = kwargs["company_name"]
    subdomain = kwargs["subdomain"]
    admin_password = kwargs["password"]
    fname = kwargs["first_name"]
    lname = kwargs["last_name"]
    email = kwargs["email"]
    phone = kwargs["phone"]
    allow_creating_users = "yes" if "allow_creating_users" in kwargs else "no"
    config = frappe.get_doc("SaaS settings")
    if not subdomain:
        return "SUBDOMAIN_NOT_PROVIDED"
    if not admin_password:
            return "ADMIN_PASSWORD_NOT_PROVIDED"
    if True:
        
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
    if(allow_creating_users == "yes"):
        create_user(
        first_name=fname,
        last_name=lname,
        email=email,
        site=subdomain + "." + frappe.conf.domain,
        phone=phone,
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
        "bench --site {} clear-cache".format(target_site.subdomain + "." + frappe.conf.domain)
    )
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
        "cd /home/{}/frappe-bench/sites & mv {}.{} {}".format(
            config.server_user_name,target_site.subdomain, frappe.conf.domain, new_site
        )
    )
    site_defaults = frappe.get_doc("SaaS settings")
    commands.append(
        "bench --site {} set-config max_users {}".format(
            new_site, site_defaults.default_user_limit
        )
    )
    # enable scheduler
    commands.append(
        "bench --site {} enable-scheduler".format(new_site)
    )
    commands.append(
        "bench --site {} set-config customer_email {}".format(
            new_site, email
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
            "bench --site {} set-config country {}".format(new_site, kwargs["country"])
        )
    commands.append(
        "bench --site {} set-config creation_date {}".format(new_site, frappe.utils.nowdate())
    )
    commands.append("bench --site {} set-maintenance-mode off".format(new_site))
    commands.append(
        "bench --site {} execute bettersaas.bettersaas.doctype.saas_sites.saas_sites.markSiteAsUsed --args {}".format(
            frappe.local.site , target_site.subdomain
        )
    )
    commands.append("bench setup nginx --yes")
    # enque long running tasks - executeCommands 
    executeCommands(commands)
    new_site_doc = frappe.new_doc("SaaS sites")
    enc_key = encrypt(admin_password, frappe.conf.enc_key)
    new_site_doc.encrypted_password = enc_key
    new_site_doc.linked_email = email
    new_site_doc.site_name = new_site
    new_site_doc.expiry_date = expiry_date
    subscription = StripeSubscriptionManager(kwargs["country"])
    customer = subscription.create_customer( new_site,email,fname,lname,phone)
    new_site_doc.cus_id = customer.id
    frappe.utils.execute_in_shell("bench --site {} set-config customer_id {}".format(new_site,customer.id))
    frappe.utils.execute_in_shell("bench --site {} set-config has_subscription {}".format(new_site,"yes"))
    # create trial subscription
    subscription.start_free_trial_of_site(customer.id)
    
    sub = subdomain
    new_site_doc.save(ignore_permissions=True)
    
    if frappe.conf.subdomain == "localhost":
        sub = target_site.subdomain
    from clientside.stripe import hasActiveSubscription
    hasActiveSubscription(invalidate_cache=True,site=new_site)
    # create Lead on this site
    lead_doc = frappe.new_doc("Lead")
    lead_doc.lead_name = fname + " " + lname
    lead_doc.email_id = email
    lead_doc.mobile_no = phone
    lead_doc.phone = phone
    lead_doc.country = kwargs["country"]
    lead_doc.company_name = new_site
    lead_doc.save(ignore_permissions=True)
    lead_doc.website = "https://" + sub + "." + frappe.conf.domain
    
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

@frappe.whitelist(allow_guest=True)
def take_backup_of_site(sitename,is_manual=0):
    command = (
        "bench --site {} execute clientside.clientside.utils.take_backups_s3 ".format(
            sitename
        )
    )
    frappe.utils.execute_in_shell(command)
    return "executing command: " + command

@frappe.whitelist()
def backup():
    sites = frappe.get_all("SaaS sites", filters={"do_backup": 1}, fields=["site_name"])
    
    for site in sites:
        print("backing up site", site.site_name)
        if site.site_name == "dff.localhost":
            continue
        frappe.enqueue("bettersaas.bettersaas.doctype.saas_sites.saas_sites.take_backup_of_site",sitename=site.site_name,at_front=1)
    return "done"
def insert_backup_record(site,backup_size,key,is_manual):
    is_manual = int(is_manual)
    import datetime
    try:
        doc = frappe.new_doc("SaaS site backups")
        doc.site_name = site
        doc.created_on = frappe.utils.now_datetime()
        doc.site_files = key
        doc.time = frappe.utils.now_datetime().strftime("%H:%M:%S")
        doc.site = site
        doc.backup_size = backup_size
        if is_manual:
            doc.created_by_user = 1
        doc.save(ignore_permissions=True)
    except Exception as e:
        print("hey", e)

@frappe.whitelist(allow_guest=True)
def delete_site(*args, **kwargs):
    print("DELETING SITE", kwargs)
    doc = frappe.get_doc("SaaS sites", {"site_name": kwargs["site_name"]})
    doc.site_deleted  = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "done"

@frappe.whitelist(allow_guest=True,methods=["POST"])
def upgrade_user(*args, **kwargs):
    print("upgrading user")
    site = kwargs["site_name"]
    user_count = kwargs["user_count"]
    product_id = kwargs["product_id"]
    site_doc = frappe.get_doc("SaaS sites", {"site_name": site})
    site_doc.plan = product_id
    site_doc.user_limit = user_count
    site_doc.save(ignore_permissions=True)
    return "done"
    
    
@frappe.whitelist(allow_guest=True)
def get_site_backup_size(sitename):
    docs = frappe.db.get_list("SaaS site backups",filters={"site":sitename,"created_by_user":1},fields=["backup_size"],ignore_permissions=True)
    return sum([float(doc.backup_size[:-1]) for doc in docs])

@frappe.whitelist(allow_guest=True)
def download_backup(backupid,site_name):
    import boto3
    
    conn = boto3.client('s3',aws_access_key_id=frappe.conf.aws_access_key_id,aws_secret_access_key=frappe.conf.aws_secret_access_key)
    backup_doc = frappe.get_doc("SaaS site backups",backupid)
    files = [backup_doc.site_files,backup_doc.database_files,backup_doc.private_files]
    file_names = [x.split("/")[-1] for x in files]
    for i in range(len(files)):
      #  print("downloading file",files[i])
        key = "site_backups/"+ site_name+"/"+files[i]
        print(key)
        conn.download_file(frappe.conf.aws_bucket_name,"site_backups/"+ site_name+"/"+files[i],file_names[i])
    # run command to restore
    return file_names
@frappe.whitelist(allow_guest=True)
def restore_site(*args, **kwargs):
    config = frappe.get_doc("SaaS settings")
    print(kwargs)
    site_name = kwargs["site_name"]
    file_names = download_backup(kwargs["backupid"],site_name)
    command_to_restore = "bench --site {} --force restore {} --with-public-files {} --with-private-files {} --db-root-password {}".format(site_name,file_names[1],file_names[0],file_names[2],config.db_password)
    frappe.enqueue("bettersaas.bettersaas.doctype.saas_sites.saas_sites.execute_command_async",command =command_to_restore,at_front=1,queue="short")
  #  resp = frappe.utils.execute_in_shell(command_to_restore)
  #  print(resp)
    # enque
    os.system(command_to_restore)
    frappe.publish_realtime("site_restored",{"site_name":site_name},user=frappe.session.user)
    return "restored"
    
def execute_command_async(command):
    frappe.utils.execute_in_shell(command)
def create_new_site_from_backup(*args, **kwargs):
    ## to do rishabh
    backupid = kwargs["backupid"]
    old_site_name = kwargs["old_site_name"]
    new_site_name = kwargs["new_site_name"]
    admin_password = kwargs["admin_password"]
    file_names = download_backup(backupid,old_site_name)
    config = frappe.get_doc("SaaS settings")
    command_from_sql_source = "bench new-site {} --source_sql {} --install-app erpnext --admin-password {} --db-root-password {}".format(new_site_name,file_names[1],admin_password,config.db_password)
    command_to_add_clientside = "bench --site {} install-app clientside".format(new_site_name)
    command_to_add_files = "bench --site {} --force restore {} --with-public-files {} --with-private-files {}".format(new_site_name,file_names[1],file_names[0],file_names[2])
    command_to_add_files = "bench --site {} --force restore {} --with-public-files {} --with-private-files {}".format(new_site_name,file_names[1],file_names[0],file_names[2])
    resp = frappe.utils.execute_in_shell(command_from_sql_source)
    print(resp)
    resp = frappe.utils.execute_in_shell(command_to_add_files)
    print(resp)
    
    
@frappe.whitelist(allow_guest=True)
def delete_old_backups(limit,site_name,created_by_user=1):
    print("deleting old backups",limit,site_name)
    limit = int(limit)
    # we delete the old backups and keep only the latest "limit" backups
    records = frappe.get_list("SaaS site backups",filters={"site":site_name,"created_by_user":created_by_user},fields=["name","created_on"],order_by="created_on desc",ignore_permissions=True)
    for i in range(limit,len(records)):
        print("deleting",records[i].name)
        frappe.delete_doc("SaaS site backups",records[i].name)
        frappe.db.commit()
    return "deletion done"
@frappe.whitelist()
def getLimitsOfSite(site_name):
    users =  frappe.get_site_config(site_path=site_name).get("max_users")
    emails = frappe.get_site_config(site_path=site_name).get("max_email")
    space = frappe.get_site_config(site_path=site_name).get("max_space")
    plan  = frappe.get_site_config(site_path=site_name).get("plan")
    return {"users":users,"emails":emails,"space":space,"plan":plan}


    
   
class SaaSsites(Document):
    pass
