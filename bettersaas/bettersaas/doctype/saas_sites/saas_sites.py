# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
import json
import os
import boto3
import re
import requests
import subprocess as sp
from bettersaas.bettersaas.doctype.saas_users.saas_users import create_user
from frappe import _
from frappe.utils import get_bench_path
from frappe.core.doctype.user.user import test_password_strength
from frappe.utils import validate_email_address
from frappe.utils.password import decrypt, encrypt
from frappe.model.document import Document

@frappe.whitelist()
def get_users_list(site_name):
    from frappe.frappeclient import FrappeClient
    site = frappe.db.get("SaaS Sites", filters={"site_name": site_name})
    site_password = decrypt(site.encrypted_password, frappe.conf.encryption_key)
    conn = FrappeClient("http://"+site_name, "Administrator", site_password)
    total_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name', 'enabled', 'last_active','user_type'],limit_page_length=10000)
    active_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name','last_active','user_type'], filters = {'enabled':'1'},limit_page_length=10000)
    return {"total_users":total_users, "active_users":active_users}

@frappe.whitelist()
def login(name):
	return frappe.get_doc("SaaS Sites",name).get_login_sid()
    
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
    sites_path = os.path.join(get_bench_path(), "sites")
    commands.append(
        "cd {} & mv {}.{} {}".format(
            sites_path, target_site.subdomain, frappe.conf.domain, new_site
        )
    )
    if kwargs["country"] == "IN":
        commands.append(
            "bench --site {} set-config min_license {}".format(
                new_site, saas_settings.default_license_limit_in
            )
        )
    else:
        commands.append(
            "bench --site {} set-config min_license {}".format(
                new_site, saas_settings.default_license_limit
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
    commands.append(
        "bench --site {} set-config country {}".format(new_site, kwargs["country"])
    )
    commands.append(
        "bench --site {} set-config created_on {}".format(
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
    execute_commands(commands)

    new_site_doc = frappe.new_doc("SaaS Sites")
    encrypted_password = encrypt(admin_password, frappe.conf.encryption_key)
    new_site_doc.site_name = new_site.lower()
    new_site_doc.country = kwargs["country"]
    new_site_doc.linked_email = email
    new_site_doc.encrypted_password = encrypted_password
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
    new_site_doc.save(ignore_permissions=True)
    frappe.db.commit()

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
        if key in ["min_license", "max_email", "max_storage"]:
            commands.append(
                "bench --site {} set-config {} {}".format(
                    kwargs["site_name"], key, value
                )
            )
    os.system(" & ".join(commands))

@frappe.whitelist()
def get_decrypted_password(*args, **kwargs):
    site = frappe.db.get("SaaS Sites", filters={"site_name": kwargs["site_name"]})
    return decrypt(site.encrypted_password, frappe.conf.enc_key)

def insert_backup_record(site, backup_path, backup_size, encrypt_backup):
    try:
        doc = frappe.new_doc("SaaS Sites Backup")
        doc.created_on = frappe.utils.now()
        doc.site = site
        doc.path = backup_path
        doc.size = backup_size
        doc.encrypted = encrypt_backup
        doc.save(ignore_permissions=True)
    except Exception as e:
        print("Error while inserting backup record", e)

def convert_to_bytes(size):
    if size == "0":
        return 0
    prefix = size[-1]
    if prefix == "G":
        return float(size[:-1]) * 1024 * 1024 * 1024
    if prefix == "M":
        return float(size[:-1]) * 1024 * 1024
    if prefix == "K":
        return float(size[:-1]) * 1024
    return float(size)

@frappe.whitelist(allow_guest=True)
def get_site_backup_size(site_name):
    docs = frappe.db.get_list(
        "SaaS Sites Backup",
        filters={"site": site_name},
        fields=["size"],
        ignore_permissions=True,
    )
    total_size = sum(
        float(convert_to_bytes(doc["size"])) for doc in docs if doc["size"] is not None
    )
    return total_size

def execute_command_async(command):
    frappe.utils.execute_in_shell(command)

def delete_from_s3(key):
    from botocore.exceptions import ClientError

    S3_CLIENT = boto3.client(
        's3',
        aws_access_key_id=frappe.conf.aws_access_key_id,
        aws_secret_access_key=frappe.conf.aws_secret_access_key,
        region_name=frappe.conf.aws_bucket_region_name,
    )
    try:
        S3_CLIENT.delete_object(
            Bucket=frappe.conf.aws_bucket_name,
            Key=key
        )
    except ClientError:
        frappe.throw(frappe._("Access denied: Could not delete file"))

@frappe.whitelist(allow_guest=True)
def delete_old_backups(site_name, limit):
    records = frappe.get_list(
        "SaaS Sites Backup",
        filters={"site": site_name},
        fields=["name", "path", "created_on"],
        order_by="created_on desc",
        ignore_permissions=True,
    )
    for i in range(int(limit), len(records)):
        frappe.delete_doc("SaaS Sites Backup", records[i].name)
        frappe.db.commit()
        delete_from_s3(records[i].path)
    return "Deletion Done"

@frappe.whitelist(allow_guest=True)
def user_contacted(site_name):
    return frappe.db.get_value("SaaS Sites", site_name, "user_contacted")

@frappe.whitelist()
def get_limits(site_name):
    users = frappe.get_site_config(site_path=site_name).get("min_license")
    emails = frappe.get_site_config(site_path=site_name).get("max_email")
    storage = frappe.get_site_config(site_path=site_name).get("max_storage")
    plan = frappe.get_site_config(site_path=site_name).get("plan")
    return {"users": users, "emails": emails, "storage": storage, "plan": plan}
class SaaSSites(Document):
    def __init__(self, *args, **kwargs):
        super(SaaSSites, self).__init__(*args, **kwargs)
        self.site_config = frappe.get_site_config(site_path=self.site_name)

    @property
    def license_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("min_license")

    @property
    def email_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_email")

    @property
    def storage_limit(self):
        return frappe.get_site_config(site_path=self.site_name).get("max_storage")
        
    @property
    def subscription_starts_on(self):
        return frappe.get_site_config(site_path=self.site_name).get("subscription_starts_on")

    @property
    def subscription_ends_on(self):
        return frappe.get_site_config(site_path=self.site_name).get("subscription_ends_on")

    @property
    def customer_id(self):
        return frappe.get_site_config(site_path=self.site_name).get("customer_id")
    
    @property
    def subscription_id(self):
        return frappe.get_site_config(site_path=self.site_name).get("subscription_id")
    
    @property
    def plan_name(self):
        return frappe.get_site_config(site_path=self.site_name).get("plan_name")
    
    @property
    def subscription_status(self):
        return frappe.get_site_config(site_path=self.site_name).get("subscription_status")

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