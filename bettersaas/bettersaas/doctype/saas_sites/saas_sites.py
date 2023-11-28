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
import subprocess as sp
import requests
from frappe.utils import today, nowtime, add_days, get_formatted_email
from clientside.stripe import StripeSubscriptionManager
from bettersaas.bettersaas.api import upgrade_site
		
@frappe.whitelist()
def get_users_list(site_name):
    saas_settings = frappe.get_doc("SaaS settings")
    site = frappe.db.get("SaaS sites", filters={"site_name": site_name})
    site_password = decrypt(site.encrypted_password, frappe.conf.enc_key)
    domain = site_name
    from bettersaas.bettersaas.doctype.saas_sites.frappeclient import FrappeClient
    conn = FrappeClient("https://"+domain, "Administrator", site_password)
    total_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name', 'enabled', 'last_active','user_type'],limit_page_length=10000)
    active_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name','last_active','user_type'], filters = {'enabled':'1'},limit_page_length=10000)
    return {"total_users":total_users, "active_users":active_users}

@frappe.whitelist()
def login(name,reason=None):
	return frappe.get_doc("SaaS sites",name).get_login_sid()
    
@frappe.whitelist()
def delete_thesite(site_name):
    commands = []
    config = frappe.get_doc("SaaS settings")
    dbpass=config.get_password("db_password")
    commands.append("bench drop-site {site} --db-root-password {dbrootpass}".format(site=site_name, dbrootpass=dbpass))
    executeCommands(commands)
    frappe.msgprint('Site Deleted !')

@frappe.whitelist()
def disable_enable_site(site_name, status):
    commands=[]
    if status == "Active":
        commands.append("bench --site {site_name} set-maintenance-mode on".format(site_name=site_name))
    else:
        commands.append("bench --site {site_name} set-maintenance-mode off".format(site_name=site_name))
    executeCommands(commands)

    
    
@frappe.whitelist(allow_guest=True)
def markSiteAsUsed(site):
    doc = frappe.get_last_doc("SaaS stock sites", filters={"subdomain": site})
    # delete the doc
    frappe.delete_doc("SaaS stock sites", doc.name)


def executeCommands(commands):
    config = frappe.get_doc("SaaS settings")
    config.db_password = config.get_password("db_password")
    config.root_password = config.get_password("root_password")
    command = " ; ".join(commands)
    process = sp.Popen(command, shell=True)
    process.wait()
    config.root_password = config.get_password("root_password")
    if frappe.conf.domain != "localhost":
        os.system(
            "echo {} | sudo -S sudo service nginx reload".format(config.root_password)
        )


@frappe.whitelist(allow_guest=True)
def check_subdomain():
    restricted_subdomains = frappe.get_doc("SaaS settings").restricted_subdomains.split(
        "\n"
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
    regex = "^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$"
    if re.search(regex, email):
        return True
    else:
        return True


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
    saas_user = None
    if allow_creating_users == "yes":
        saas_user = create_user(
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
    if len(stock_sites) == 0:
        # call refresh stock sites
        # keep checking each second if we have at least one stock site
        # if yes then continue the code
        # else keep checking
        import time

        while True:
            time.sleep(1)
            stock_sites = frappe.db.get_list(
                "SaaS stock sites", filters={"is_used": "no"}, ignore_permissions=True
            )
            if len(stock_sites) > 0:
                break
            from bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites import (
                refreshStockSites,
            )

            refreshStockSites()

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
        "bench --site {} clear-cache".format(
            target_site.subdomain + "." + frappe.conf.domain
        )
    )
    import re

    def escape_dollar_sign(input_string):
        return re.sub(r'\$', r'\\$', input_string) if '$' in input_string else input_string

    pass_value = str(admin_password)
    escaped_pass = escape_dollar_sign(pass_value)

    commands.append(
        "bench --site {} set-admin-password {}".format(
            target_site.subdomain + "." + frappe.conf.domain, escaped_pass
        )
    )
    commands.append(
        "bench setup add-domain {} --site {} ".format(
            new_site, target_site.subdomain + "." + frappe.conf.domain
        )
    )
    commands.append(
        "cd /home/{}/frappe-bench/sites & mv {}.{} {}".format(
            config.server_user_name, target_site.subdomain, frappe.conf.domain, new_site
        )
    )
    site_defaults = frappe.get_doc("SaaS settings")
    commands.append(
        "bench --site {} set-config max_users {}".format(
            new_site, site_defaults.default_user_limit
        )
    )
    # enable scheduler
    commands.append("bench --site {} enable-scheduler".format(new_site))
    commands.append(
        "bench --site {} set-config customer_email {}".format(new_site, email)
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
        "bench --site {} set-config creation_date {}".format(
            new_site, frappe.utils.nowdate()
        )
    )
    commands.append("bench --site {} set-maintenance-mode off".format(new_site))
    commands.append(
        "bench --site {} execute bettersaas.bettersaas.doctype.saas_sites.saas_sites.markSiteAsUsed --args {}".format(
            frappe.local.site, target_site.subdomain
        )
    )
    commands.append("bench setup nginx --yes")
    # enque long running tasks - executeCommands
    executeCommands(commands)
    new_site_doc = frappe.new_doc("SaaS sites")
    enc_key = encrypt(admin_password, frappe.conf.enc_key)
    new_site_doc.encrypted_password = enc_key
    new_site_doc.linked_email = email
    new_site_doc.site_name = new_site.lower()
    new_site_doc.expiry_date = expiry_date

    # new_site_doc.site_user=email
    new_site_doc.number_of_active_users=1
    new_site_doc.number_of_users=1
    new_site_doc.user_details = []
    new_site_doc.append('user_details', {
        'first_name': fname,
        'last_name': lname,
        'user_type': 'System User',
        'active': 1,
        'email_id': email,
        'last_active': ''
    })
    
    new_site_doc.saas_user = saas_user.name if saas_user else None
    subscription = StripeSubscriptionManager(kwargs["country"])
    customer = subscription.create_customer(new_site, email, fname, lname, phone)
    new_site_doc.cus_id = customer.id
    frappe.utils.execute_in_shell(
        "bench --site {} set-config customer_id {}".format(new_site, customer.id)
    )
    frappe.utils.execute_in_shell(
        "bench --site {} set-config has_subscription {}".format(new_site, "yes")
    )
    # create trial subscription
    new_site_doc.save(ignore_permissions=True)

    # link new site doc with stock site doc ( Linked documents)
    sub = subdomain
    try:
        # lead_doc = frappe.new_doc("Lead")
        # lead_doc.lead_name = fname + " " + lname
        # lead_doc.mobile_no = phone
        # lead_doc.phone = phone
        # # find if lead email already exists
        # doc = frappe.db.get_list(
        #     "Lead",
        #     filters={"lead_email": email},
        #     fields=["name"],
        #     ignore_permissions=True,
        # )
        # if len(doc) == 0:
        #     lead_doc.email = email

        # lead_doc.lead_email = email
        # lead_doc.company_name = new_site
        # lead_doc.website = "https://" + sub + "." + frappe.conf.domain
        # lead_doc.save(ignore_permissions=True)
        pass
    except Exception as e:
        print("lead already exists")
    if frappe.conf.subdomain == "localhost":
        sub = target_site.subdomain
    frappe.db.commit()
    # create stripe subscription
    subscription.start_free_trial_of_site(customer.id)
    from clientside.stripe import hasActiveSubscription

    hasActiveSubscription(invalidate_cache=True, site=new_site)

    # send mail to user
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
    if len(site) > 0:
        return "yes"
    else:
        return "no"


@frappe.whitelist()
def updateLimitsOfSite(*args, **kwargs):
    commands = []
    for key, value in kwargs.items():
        if key in ["max_users", "max_email", "max_space", "expiry_date"]:
            commands.append(
                "bench --site   {} set-config {} {}".format(
                    kwargs["sitename"], key, value
                )
            )
    os.system(" & ".join(commands))


@frappe.whitelist()
def getDecryptedPassword(*args, **kwargs):
    site = frappe.db.get("SaaS sites", filters={"site_name": kwargs["site_name"]})
    return decrypt(site.encrypted_password, frappe.conf.enc_key)


@frappe.whitelist(allow_guest=True)
def take_backup_of_site(sitename, is_manual=0):
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
        frappe.enqueue(
            "bettersaas.bettersaas.doctype.saas_sites.saas_sites.take_backup_of_site",
            sitename=site.site_name,
            at_front=1,
        )
    return "done"

# def update_user_to_main_app():
#     admin_site_name = "app.onehash.store"
#     frappe.destroy()
#     frappe.init(site=admin_site_name)
#     frappe.connect()
#     all_sites = frappe.get_all("SaaS sites")
#     for site in all_sites:
#         frappe.destroy()
#         current_site_name = site.name
#         print(current_site_name)
#         frappe.init(site=current_site_name)
#         frappe.connect()
#         enabled_system_users = frappe.get_all("User",fields=['name','email','last_active','user_type','enabled','first_name','last_name','creation'])
        
#         frappe.destroy()
#         frappe.init(site=admin_site_name)
#         frappe.connect()        
#         try:        
#             site_doc = frappe.get_doc('SaaS sites',current_site_name)
#             site_doc.user_details = {}        
#             enabled_users_count = 0
#             max_last_active = None
#             for user in enabled_system_users:                       
#                 if(user.name in ['Administrator','Guest']):
#                     continue

#                 site_doc.append('user_details', {
#                     'first_name': user.first_name,
#                     'last_name': user.last_name,
#                     'user_type': user.user_type,
#                     'active': user.enabled,
#                     'email_id': user.email,
#                     'last_active':user.last_active
#                 })

#                 if(user.enabled):
#                     enabled_users_count = enabled_users_count + 1

#                 if(user.last_active==None):
#                     continue

#                 if(max_last_active==None):
#                     max_last_active = user.last_active
#                 elif(max_last_active<user.last_active):
#                     max_last_active = user.last_active

#             site_doc.number_of_users =   (len(enabled_system_users)-2)
#             site_doc.number_of_active_users= enabled_users_count
#             site_doc.save()
#             frappe.db.commit()            
#         except Exception as e:
#             frappe.log_error(str(e))
#         finally:
#             frappe.destroy()

def insert_backup_record(site, backup_size, key, is_manual):
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
    doc = frappe.get_doc("SaaS sites", {"site_name": kwargs["site_name"]})
    doc.site_deleted = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "done"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upgrade_user(*args, **kwargs):
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
    docs = frappe.db.get_list(
        "SaaS site backups",
        filters={"site": sitename, "created_by_user": 1},
        fields=["backup_size"],
        ignore_permissions=True,
    )
    from clientside.clientside.utils import convertToB

    return sum([float(convertToB(doc.backup_size)) for doc in docs])


@frappe.whitelist(allow_guest=True)
def download_backup(backupid, site_name):
    import boto3

    conn = boto3.client(
        "s3",
        aws_access_key_id=frappe.conf.aws_access_key_id,
        aws_secret_access_key=frappe.conf.aws_secret_access_key,
    )
    backup_doc = frappe.get_doc("SaaS site backups", backupid)
    files = [backup_doc.site_files, backup_doc.database_files, backup_doc.private_files]
    file_names = [x.split("/")[-1] for x in files]
    for i in range(len(files)):
        key = "site_backups/" + site_name + "/" + files[i]
        print(key)
        conn.download_file(
            frappe.conf.aws_bucket_name,
            "site_backups/" + site_name + "/" + files[i],
            file_names[i],
        )
    # run command to restore
    return file_names


@frappe.whitelist(allow_guest=True)
def restore_site(*args, **kwargs):
    config = frappe.get_doc("SaaS settings")
    site_name = kwargs["site_name"]
    file_names = download_backup(kwargs["backupid"], site_name)
    command_to_restore = "bench --site {} --force restore {} --with-public-files {} --with-private-files {} --db-root-password {}".format(
        site_name, file_names[1], file_names[0], file_names[2], config.db_password
    )
    frappe.enqueue(
        "bettersaas.bettersaas.doctype.saas_sites.saas_sites.execute_command_async",
        command=command_to_restore,
        at_front=1,
        queue="short",
    )
    os.system(command_to_restore)
    frappe.publish_realtime(
        "site_restored", {"site_name": site_name}, user=frappe.session.user
    )
    return "restored"


def execute_command_async(command):
    frappe.utils.execute_in_shell(command)


def create_new_site_from_backup(*args, **kwargs):
    ## to do rishabh
    backupid = kwargs["backupid"]
    old_site_name = kwargs["old_site_name"]
    new_site_name = kwargs["new_site_name"]
    admin_password = kwargs["admin_password"]
    file_names = download_backup(backupid, old_site_name)
    config = frappe.get_doc("SaaS settings")
    command_from_sql_source = "bench new-site {} --source_sql {} --install-app erpnext --admin-password {} --db-root-password {}".format(
        new_site_name, file_names[1], admin_password, config.db_password
    )
    command_to_add_clientside = "bench --site {} install-app clientside".format(
        new_site_name
    )
    command_to_add_files = "bench --site {} --force restore {} --with-public-files {} --with-private-files {}".format(
        new_site_name, file_names[1], file_names[0], file_names[2]
    )
    command_to_add_files = "bench --site {} --force restore {} --with-public-files {} --with-private-files {}".format(
        new_site_name, file_names[1], file_names[0], file_names[2]
    )
    resp = frappe.utils.execute_in_shell(command_from_sql_source)
    resp = frappe.utils.execute_in_shell(command_to_add_files)


@frappe.whitelist(allow_guest=True)
def delete_old_backups(limit, site_name, created_by_user=1):
    print("deleting old backups", limit, site_name)
    limit = int(limit)
    # we delete the old backups and keep only the latest "limit" backups
    records = frappe.get_list(
        "SaaS site backups",
        filters={"site": site_name, "created_by_user": created_by_user},
        fields=["name", "created_on"],
        order_by="created_on desc",
        ignore_permissions=True,
    )
    for i in range(limit, len(records)):
        frappe.delete_doc("SaaS site backups", records[i].name)
        frappe.db.commit()
    return "deletion done"


@frappe.whitelist()
def getLimitsOfSite(site_name):
    users = frappe.get_site_config(site_path=site_name).get("max_users")
    emails = frappe.get_site_config(site_path=site_name).get("max_email")
    space = frappe.get_site_config(site_path=site_name).get("max_space")
    plan = frappe.get_site_config(site_path=site_name).get("plan")
    return {"users": users, "emails": emails, "space": space, "plan": plan}


class SaaSsites(Document):
    def __init__(self, *args, **kwargs):
        super(SaaSsites, self).__init__(*args, **kwargs)
        self.site_config = frappe.get_site_config(site_path=self.site_name)
        stripe = StripeSubscriptionManager(self.site_config.get("country"))
        self.subcription = stripe.get_onehash_subscription(self.cus_id)

    @property
    def user_limit(self):
        return (
            "Unlimited"
            if self.plan == "ONEHASH_PRO"
            else frappe.get_site_config(site_path=self.site_name).get("max_users")
        )

    @property
    def email_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_email")

    @property
    def space_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_space")
        
    @property
    def current_period_start(self):
        import datetime

        sub = self.subcription
        if sub == "NONE":
            return ""
        return datetime.datetime.fromtimestamp(sub["current_period_start"])

    @property
    def current_period_end(self):
        import datetime

        sub = self.subcription
        if sub == "NONE":
            return ""
        return datetime.datetime.fromtimestamp(sub["current_period_end"])

    @property
    def days_left_in_current_period(self):
        import datetime

        if self.subcription == "NONE":
            return ""
        end_date = self.current_period_end
        return (end_date - datetime.datetime.now()).days

    @property
    def subscription_id(self):
        if self.subcription == "NONE":
            return ""
        return self.subcription["id"]

    @property
    def plan(self):
        return self.site_config.get("plan") or "Free"

    @property
    def subscription_status(self):
        if self.subcription == "NONE":
            return "No subscription"
        return self.subcription["status"].capitalize()

    @property
    def linked_domains(self):
        domains = frappe.get_site_config(site_path=self.site_name).get("domains")
        ret = []
        for key in domains.keys():
            if type(key) == dict:
                ret.append(domains[key]["domain"])
            else:
                ret.append(key)
        return "\n".join(ret)
    
    @frappe.whitelist()
    def get_login_sid(self):
        site = frappe.db.get("SaaS sites", filters={"site_name": self.name})
        password = decrypt(site.encrypted_password, frappe.conf.enc_key)
        response = requests.post(
            f"https://{self.name}/api/method/login",
            data={"usr": "Administrator", "pwd": password},
        )
        sid = response.cookies.get("sid")
        if sid:
            return sid
            
    def update_limits(self):
        frappe.msgprint("updating limits")
        return
