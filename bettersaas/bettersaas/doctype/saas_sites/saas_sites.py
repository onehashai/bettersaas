# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
import json
import os
import re
import requests
import subprocess as sp
from bettersaas.api import upgrade_site
from bettersaas.bettersaas.doctype.saas_users.saas_users import create_user
# from clientside.stripe import StripeSubscriptionManager
from frappe.core.doctype.user.user import test_password_strength
from frappe.utils import validate_email_address
from frappe.utils.password import decrypt, encrypt
from frappe.model.document import Document
from frappe.utils import today, nowtime, add_days, get_formatted_email
		
@frappe.whitelist()
def get_users_list(site_name):
    # from bettersaas.bettersaas.doctype.saas_sites.frappeclient import FrappeClient
    from frappe.frappeclient import FrappeClient
    site = frappe.db.get("SaaS Sites", filters={"site_name": site_name})
    site_password = decrypt(site.encrypted_password, frappe.conf.enc_key)
    conn = FrappeClient("https://"+site_name, "Administrator", site_password)
    total_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name', 'enabled', 'last_active','user_type'],limit_page_length=10000)
    active_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name','last_active','user_type'], filters = {'enabled':'1'},limit_page_length=10000)
    return {"total_users":total_users, "active_users":active_users}

@frappe.whitelist()
def login(name,reason=None):
	return frappe.get_doc("SaaS Sites",name).get_login_sid()
    
@frappe.whitelist()
def delete_site(site_name):
    commands = []
    root_password = frappe.conf.root_password
    commands.append("bench drop-site {site} --db-root-password {root_pass}".format(site=site_name, root_pass=root_password))
    execute_commands(commands)
    frappe.msgprint('Site Deleted !')

@frappe.whitelist()
def disable_enable_site(site_name, status):
    commands=[]
    if status == "Active":
        commands.append("bench --site {site_name} set-maintenance-mode on".format(site_name=site_name))
    else:
        commands.append("bench --site {site_name} set-maintenance-mode off".format(site_name=site_name))
    execute_commands(commands)

@frappe.whitelist(allow_guest=True)
def mark_site_as_used(site):
    doc = frappe.get_last_doc("SaaS Stock Sites", filters={"subdomain": site})
    frappe.delete_doc("SaaS Stock Sites", doc.name)

def execute_commands(commands):
    command = " ; ".join(commands)
    process = sp.Popen(command, shell=True)
    process.wait()
    os.system(
        "echo {} | sudo -S sudo service nginx reload".format(frappe.conf.get("root_password"))
    )

@frappe.whitelist(allow_guest=True)
def check_subdomain():
    restricted_subdomains = frappe.get_doc("SaaS Settings").restricted_subdomains.split(
        "\n"
    )
    site = frappe.get_all(
        "SaaS Sites",
        filters={
            "site_name": frappe.form_dict.get("subdomain") + "." + frappe.conf.domain
        },
    )
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
    user_data = (first_name, "", last_name, email, "")
    if "'" in passphrase or '"' in passphrase:
        return {
            "feedback": {
                "password_policy_validation_passed": False,
                "suggestions": ["Password should not contain ' or \""],
            }
        }
    return test_password_strength(passphrase, user_data=user_data)

def escape_dollar_sign(input_string):
    return re.sub(r'\$', r'\\$', input_string) if '$' in input_string else input_string

@frappe.whitelist(allow_guest=True)
def setup_site(*args, **kwargs):
    company_name = kwargs["company_name"]
    subdomain = kwargs["subdomain"]
    admin_password = kwargs["password"]
    fname = kwargs["first_name"]
    lname = kwargs["last_name"]
    email = kwargs["email"]
    phone = kwargs["phone"]
    allow_creating_users = kwargs["allow_creating_users"]
    saas_settings = frappe.get_doc("SaaS Settings")
    if not subdomain:
        return "SUBDOMAIN_NOT_PROVIDED"
    if not admin_password:
        return "ADMIN_PASSWORD_NOT_PROVIDED"
    if not fname:
        return "FIRST_NAME_NOT_PROVIDED"
    if not lname:
        return "LAST_NAME_NOT_PROVIDED"
    if validate_email_address(email) == '':
        return "EMAIL_NOT_PROVIDED"
    if not company_name:
        return "COMPANY_NAME_NOT_PROVIDED"
    password_check_result = check_password_strength(
        password=admin_password,
        first_name=fname,
        last_name=lname,
        email=email
    )
    if not password_check_result["feedback"]["password_policy_validation_passed"]:
        return "PASSWORD_NOT_STRONG"
    new_site = subdomain + "." + frappe.conf.domain
    saas_user = None
    if allow_creating_users:
        saas_user = create_user(
            first_name=fname,
            last_name=lname,
            email=email,
            site=subdomain + "." + frappe.conf.domain,
            phone=phone,
        )

    stock_sites = frappe.db.get_list(
        "SaaS Stock Sites", filters={"is_used": "no"}, ignore_permissions=True
    )
    if len(stock_sites) == 0:
        import time

        while True:
            time.sleep(1)
            stock_sites = frappe.db.get_list(
                "SaaS Stock Sites", filters={"is_used": "no"}, ignore_permissions=True
            )
            if len(stock_sites) > 0:
                break
            from bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites import (
                refresh_stock_sites,
            )
            refresh_stock_sites()
    target_site = frappe.get_doc(
        "SaaS Stock Sites", stock_sites[0]["name"], ignore_permissions=True
    )
    commands = []
    commands.append(
        "bench --site {} clear-cache".format(
            target_site.subdomain + "." + frappe.conf.domain
        )
    )
    
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
    if frappe.conf.domain != "localhost":
        commands.append(
            "cd /home/{}/frappe-bench/sites & mv {}.{} {}".format(
                frappe.conf.server_user_name, target_site.subdomain, frappe.conf.domain, new_site
            )
        )
    else:
        #  Override command according to your local directory
         commands.append(
            "cd /home/{}/OneHash/onehash-crm-v15/frappe-bench/sites & mv {}.{} {}".format(
                frappe.conf.server_user_name, target_site.subdomain, frappe.conf.domain, new_site
            )
        )
    commands.append(
        "bench --site {} set-config max_users {}".format(
            new_site, saas_settings.default_user_limit
        )
    )
    commands.append(
        "bench --site {} set-config max_email {}".format(
            new_site, saas_settings.default_email_limit
        )
    )
    commands.append(
        "bench --site {} set-config max_storage {}".format(
            new_site, saas_settings.default_storage_limit
        )
    )
    commands.append(
        "bench --site {} set-config customer_email {}".format(new_site, email)
    )
    commands.append(
        "bench --site {} set-config site_name {}".format(new_site, new_site)
    )
    expiry_days = int(saas_settings.default_site_expiry_days)
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
    commands.append(
        "bench --site {} execute bettersaas.bettersaas.doctype.saas_sites.saas_sites.mark_site_as_used --args {}".format(
            frappe.local.site, target_site.subdomain
        )
    )

    commands.append("bench --site {} enable-scheduler".format(new_site))
    commands.append("bench --site {} set-maintenance-mode off".format(new_site))
    commands.append("bench setup nginx --yes")

    # enqueue long running tasks - execute_commands
    execute_commands(commands)
    new_site_doc = frappe.new_doc("SaaS Sites")
    encrypted_password = encrypt(admin_password, frappe.conf.encryption_key)
    new_site_doc.site_name = new_site.lower()
    new_site_doc.country = kwargs["country"]
    new_site_doc.linked_email = email
    new_site_doc.encrypted_password = encrypted_password
    new_site_doc.expiry_date = expiry_date
    new_site_doc.active_users=1
    new_site_doc.total_users=1
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
    # subscription = StripeSubscriptionManager(kwargs["country"])
    # customer = subscription.create_customer(new_site, email, fname, lname, phone)
    # new_site_doc.cus_id = customer.id
    # frappe.utils.execute_in_shell(
    #     "bench --site {} set-config customer_id {}".format(new_site, customer.id)
    # )
    # frappe.utils.execute_in_shell(
    #     "bench --site {} set-config has_subscription {}".format(new_site, "yes")
    # )
    # create trial subscription
    new_site_doc.save(ignore_permissions=True)

    # link new site doc with stock site doc ( Linked documents)
   
    frappe.db.commit()
    # create stripe subscription
    # subscription.start_free_trial_of_site(customer.id)
    # from clientside.stripe import hasActiveSubscription

    # hasActiveSubscription(invalidate_cache=True, site=new_site)

    # send mail to user
    return {"subdomain": subdomain, "encrypted_password": encrypted_password}

@frappe.whitelist(allow_guest=True)
def check_site_created(*args, **kwargs):
    doc = json.loads(kwargs["doc"])
    site_name = doc["site_name"]
    site = frappe.db.get_list(
        "SaaS Sites",
        filters={"site_name": site_name + "." + frappe.conf.domain},
        ignore_permissions=True,
    )
    if len(site) > 0:
        return "yes"
    else:
        return "no"

@frappe.whitelist()
def update_limits(*args, **kwargs):
    commands = []
    for key, value in kwargs.items():
        if key in ["max_users", "max_email", "max_storage", "expiry_date"]:
            commands.append(
                "bench --site   {} set-config {} {}".format(
                    kwargs["site_name"], key, value
                )
            )
    os.system(" & ".join(commands))

@frappe.whitelist()
def get_decrypted_password(*args, **kwargs):
    site = frappe.db.get("SaaS Sites", filters={"site_name": kwargs["site_name"]})
    return decrypt(site.encrypted_password, frappe.conf.enc_key)

@frappe.whitelist(allow_guest=True)
def create_backup(site_name, is_manual=0):
    command = (
        "bench --site {} execute clientside.clientside.utils.take_backups_s3 ".format(
            site_name
        )
    )
    frappe.utils.execute_in_shell(command)
    return "executing command: " + command

@frappe.whitelist()
def backup():
    sites = frappe.get_all("SaaS Sites", filters={"do_backup": 1}, fields=["site_name"])
    for site in sites:
        frappe.enqueue(
            "bettersaas.bettersaas.doctype.saas_sites.saas_sites.create_backup",
            site_name=site.site_name,
            at_front=1,
        )
    return "done"

def insert_backup_record(site, backup_size, key, is_manual):
    is_manual = int(is_manual)
    try:
        doc = frappe.new_doc("SaaS Site Backups")
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
        print("Error while inserting backup record", e)

@frappe.whitelist(allow_guest=True)
def delete_site(*args, **kwargs):
    doc = frappe.get_doc("SaaS Sites", {"site_name": kwargs["site_name"]})
    doc.site_deleted = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "done"

@frappe.whitelist(allow_guest=True, methods=["POST"])
def upgrade_user(*args, **kwargs):
    site = kwargs["site_name"]
    user_count = kwargs["user_count"]
    product_id = kwargs["product_id"]
    site_doc = frappe.get_doc("SaaS Sites", {"site_name": site})
    site_doc.plan = product_id
    site_doc.user_limit = user_count
    site_doc.save(ignore_permissions=True)
    return "done"

@frappe.whitelist(allow_guest=True)
def get_site_backup_size(site_name):
    docs = frappe.db.get_list(
        "SaaS Site Backups",
        filters={"site": site_name, "created_by_user": 1},
        fields=["backup_size"],
        ignore_permissions=True,
    )
    # from clientside.clientside.utils import convertToB

    # return sum([float(convertToB(doc.backup_size)) for doc in docs])
    return

@frappe.whitelist(allow_guest=True)
def download_backup(backup_id, site_name):
    import boto3
    conn = boto3.client(
        "s3",
        aws_access_key_id=frappe.conf.aws_access_key_id,
        aws_secret_access_key=frappe.conf.aws_secret_access_key,
    )
    backup_doc = frappe.get_doc("SaaS Site Backups", backup_id)
    files = [backup_doc.site_files, backup_doc.database_files, backup_doc.private_files]
    file_names = [x.split("/")[-1] for x in files]
    for i in range(len(files)):
        key = "site_backups/" + site_name + "/" + files[i]
        conn.download_file(
            frappe.conf.aws_bucket_name,
            "site_backups/" + site_name + "/" + files[i],
            file_names[i],
        )
    return file_names

@frappe.whitelist(allow_guest=True)
def restore_site(*args, **kwargs):
    site_name = kwargs["site_name"]
    file_names = download_backup(kwargs["backup_id"], site_name)
    command_to_restore = "bench --site {} --force restore {} --with-public-files {} --with-private-files {} --db-root-password {}".format(
        site_name, file_names[1], file_names[0], file_names[2], frappe.conf.root_password
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
    backup_id = kwargs["backup_id"]
    old_site_name = kwargs["old_site_name"]
    new_site_name = kwargs["new_site_name"]
    admin_password = kwargs["admin_password"]
    file_names = download_backup(backup_id, old_site_name)
    command_from_sql_source = "bench new-site {} --source_sql {} --install-app erpnext --admin-password {} --db-root-password {}".format(
        new_site_name, file_names[1], admin_password, frappe.config.root_password
    )
    # command_to_add_clientside = "bench --site {} install-app clientside".format(
    #     new_site_name
    # )
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
    limit = int(limit)
    # We only retain the most recent "limit" backups and remove the older ones.
    records = frappe.get_list(
        "SaaS Site Backups",
        filters={"site": site_name, "created_by_user": created_by_user},
        fields=["name", "created_on"],
        order_by="created_on desc",
        ignore_permissions=True,
    )
    for i in range(limit, len(records)):
        frappe.delete_doc("SaaS Site Backups", records[i].name)
        frappe.db.commit()
    return "deletion done"

@frappe.whitelist()
def get_limits(site_name):
    users = frappe.get_site_config(site_path=site_name).get("max_users")
    emails = frappe.get_site_config(site_path=site_name).get("max_email")
    storage = frappe.get_site_config(site_path=site_name).get("max_storage")
    plan = frappe.get_site_config(site_path=site_name).get("plan")
    return {"users": users, "emails": emails, "storage": storage, "plan": plan}
class SaaSSites(Document):
    def __init__(self, *args, **kwargs):
        super(SaaSSites, self).__init__(*args, **kwargs)
        self.site_config = frappe.get_site_config(site_path=self.site_name)
        # stripe = StripeSubscriptionManager(self.site_config.get("country"))
        # self.subcription = stripe.get_onehash_subscription(self.cus_id)

    @property
    def user_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_users")

    @property
    def email_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_email")

    @property
    def storage_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_storage")
        
    # @property
    # def current_period_start(self):
    #     import datetime

    #     sub = self.subcription
    #     if sub == "NONE":
    #         return ""
    #     return datetime.datetime.fromtimestamp(sub["current_period_start"])

    # @property
    # def current_period_end(self):
    #     import datetime

    #     sub = self.subcription
    #     if sub == "NONE":
    #         return ""
    #     return datetime.datetime.fromtimestamp(sub["current_period_end"])

    # @property
    # def days_left_in_current_period(self):
    #     import datetime

    #     if self.subcription == "NONE":
    #         return ""
    #     end_date = self.current_period_end
    #     return (end_date - datetime.datetime.now()).days

    # @property
    # def subscription_id(self):
    #     if self.subcription == "NONE":
    #         return ""
    #     return self.subcription["id"]

    # @property
    # def plan(self):
    #     return self.site_config.get("plan") or "Free"

    # @property
    # def subscription_status(self):
    #     if self.subcription == "NONE":
    #         return "No subscription"
    #     return self.subcription["status"].capitalize()

    @property
    def custom_domains(self):
        domains = frappe.get_site_config(site_path=self.site_name).get("domains")
        arr = []
        for item in domains:
            if isinstance(item, str):
                arr.append(item)
            elif isinstance(item, dict):
                domain = item.get("domain")
                if domain:
                    arr.append(domain)
        return "\n".join(arr)
    
    @frappe.whitelist()
    def get_login_sid(self):
        site = frappe.db.get("SaaS Sites", filters={"site_name": self.name})
        password = decrypt(site.encrypted_password, frappe.conf.encryption_key)
        response = requests.post(
            f"https://{self.name}/api/method/login",
            data={"usr": "Administrator", "pwd": password},
        )
        sid = response.cookies.get("sid")
        if sid:
            return sid
            
    def update_limits(self):
        frappe.msgprint("Updating Limits")
        return
