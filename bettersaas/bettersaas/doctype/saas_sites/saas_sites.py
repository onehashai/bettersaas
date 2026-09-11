# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
import json
import os
import requests
import ipaddress
import re
import subprocess as sp
from markupsafe import Markup, escape
from bettersaas.contexts.user_context import get_user_context
import bettersaas.fail2ban as f2b
from bettersaas.bettersaas import utils
from bettersaas.bettersaas.auth import verify_guest_id
from bettersaas.bettersaas.doctype.saas_users.saas_users import create_user
from frappe import utils as frappe_utils
from frappe.core.doctype.user.user import test_password_strength
from frappe.utils.password import decrypt, encrypt
from frappe.model.document import Document


@frappe.whitelist()
def get_users_list(site_name):
    from frappe.frappeclient import FrappeClient

    site = frappe.db.get("SaaS Sites", filters={"site_name": site_name})
    site_password = decrypt(site.encrypted_password, frappe.conf.encryption_key)
    conn = FrappeClient("http://" + site_name, "Administrator", site_password)
    total_users = conn.get_list(
        "User",
        fields=[
            "name",
            "first_name",
            "last_name",
            "enabled",
            "last_active",
            "user_type",
        ],
        limit_page_length=10000,
    )
    active_users = conn.get_list(
        "User",
        fields=["name", "first_name", "last_name", "last_active", "user_type"],
        filters={"enabled": "1"},
        limit_page_length=10000,
    )
    return {"total_users": total_users, "active_users": active_users}


@frappe.whitelist()
def create_user_entry_in_saas_site():
    try:
        data = frappe.local.form_dict

        site_name = data.get("site_name")
        email = data.get("email")
        firstname = data.get("firstname")
        lastname = data.get("lastname")
        user_type = data.get("user_type")
        enabled = int(data.get("enabled"))
        last_active = data.get("last_active")

        saas_site_doc = frappe.get_doc("SaaS Sites", site_name)
        for user in saas_site_doc.user_details:
            if user.email_id == email:
                return {"status": "OK", "message": "User already exists"}

        saas_site_doc.append(
            "user_details",
            {
                "first_name": firstname,
                "last_name": lastname,
                "user_type": user_type,
                "active": enabled,
                "email_id": email,
                "last_active": last_active,
            },
        )
        saas_site_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"status": "OK", "message": f"User {email} on site {site_name} created"}
    except Exception as e:
        return {"status": "FAILED", "message": str(e)}


@frappe.whitelist()
def update_user_entry_in_saas_site():
    try:
        data = frappe.local.form_dict

        site_name = data.get("site_name")
        email = data.get("email")
        firstname = data.get("firstname")
        lastname = data.get("lastname")
        user_type = data.get("user_type")
        enabled = int(data.get("enabled"))
        last_active = data.get("last_active")

        saas_site_doc = frappe.get_doc("SaaS Sites", site_name)

        found = False
        for user in saas_site_doc.user_details:
            if user.email_id == email:
                user.first_name = firstname
                user.last_name = lastname
                user.user_type = user_type
                user.active = enabled
                user.last_active = last_active
                found = True
                break

        if not found:
            saas_site_doc.append(
                "user_details",
                {
                    "first_name": firstname,
                    "last_name": lastname,
                    "user_type": user_type,
                    "active": enabled,
                    "email_id": email,
                    "last_active": last_active,
                },
            )

        saas_site_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"status": "OK", "message": f"User {email} on site {site_name} updated"}
    except Exception as e:
        return {"status": "FAILED", "message": str(e)}


@frappe.whitelist()
def delete_user_entry_in_saas_site():
    try:
        data = frappe.local.form_dict

        site_name = data.get("site_name")
        email = data.get("email")

        saas_site_doc = frappe.get_doc("SaaS Sites", site_name)

        for user in saas_site_doc.user_details:
            if user.email_id == email:
                saas_site_doc.remove(user)
                break
        saas_site_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "OK",
            "message": f"User {email} removed from site {site_name}",
        }
    except Exception as e:
        return {"status": "FAILED", "message": str(e)}


@frappe.whitelist()
def login(name):
    return frappe.get_doc("SaaS Sites", name).get_login_sid()


@frappe.whitelist()
def disable_enable_site(site_name, status):
    commands = []
    if status == "Active":
        commands.append(
            "bench --site {site_name} set-maintenance-mode on".format(
                site_name=site_name
            )
        )
    else:
        commands.append(
            "bench --site {site_name} set-maintenance-mode off".format(
                site_name=site_name
            )
        )
    execute_commands(commands)


def mark_site_as_used(site):
    doc = frappe.get_last_doc("SaaS Stock Sites", filters={"subdomain": site})
    frappe.delete_doc("SaaS Stock Sites", doc.name)


def execute_commands(commands):
    command = " && ".join(commands)
    sp.run(command, shell=True, check=True)
    os.system(
        "echo {} | sudo -S sudo service nginx reload".format(
            frappe.conf.get("root_password")
        )
    )


@frappe.whitelist(allow_guest=True)
def check_subdomain(subdomain: str | None = None):
    subdomain = subdomain or frappe.form_dict.get("subdomain")
    valid = bool(subdomain and subdomain.strip())

    if valid:
        restricted_subdomains = frappe.get_doc(
            "SaaS Settings"
        ).restricted_subdomains.split("\n")
        valid = subdomain not in restricted_subdomains

    if valid:
        site_count = frappe.db.count(
            "SaaS Sites",
            filters={"site_name": subdomain + "." + frappe.conf.domain},
        )
        if site_count > 0:
            valid = False

    if valid:
        valid = frappe_utils.validate_name(subdomain)

    if valid:
        return {"status": "success"}
    else:
        return {"status": "failed"}


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
@verify_guest_id
def setup_site(*args, **kwargs):
    try:
        company_name = utils.validate_name(
            kwargs.get("company_name"), name_label="Company Name"
        )
        fname = utils.validate_name(kwargs.get("first_name"), name_label="First Name")
        lname = utils.validate_name(kwargs.get("last_name"), name_label="Last Name")
        email = utils.validate_email_address(kwargs.get("email"))
    except Exception as e:
        return str(e)

    subdomain = frappe_utils.strip(kwargs.get("subdomain", ""))
    admin_password = kwargs.get("password")
    phone = frappe_utils.strip(kwargs.get("phone", ""))
    allow_creating_users = kwargs.get("allow_creating_users")

    saas_settings = frappe.get_doc("SaaS Settings")

    if not subdomain:
        return "SUBDOMAIN_NOT_PROVIDED"
    if check_subdomain(subdomain).get("status") == "failed":
        return "INVALID_SUBDOMAIN"

    if not phone:
        return "PHONE_NOT_PROVIDED"
    try:
        utils.validate_phone_number(phone, "Phone")
    except Exception:
        return "INVALID_PHONE"

    if not admin_password:
        return "ADMIN_PASSWORD_NOT_PROVIDED"
    password_check_result = check_password_strength(
        password=admin_password, first_name=fname, last_name=lname, email=email
    )
    if not password_check_result["feedback"]["password_policy_validation_passed"]:
        return "PASSWORD_NOT_STRONG"

    lead_doc = frappe.get_last_doc("Lead", filters={"email_id": email})
    lead_doc.site_status = "Creating Site"
    lead_doc.save(ignore_permissions=True)
    frappe.db.commit()

    new_site = subdomain + "." + frappe.conf.domain
    saas_user = None
    if allow_creating_users:
        with get_user_context("Administrator"):
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
    sites_path = os.path.join(frappe_utils.get_bench_path(), "sites")
    commands.append(
        "cd {} && mv {}.{} {}".format(
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
            new_site, frappe_utils.nowdate()
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
    new_site_doc.active_users = 1
    new_site_doc.total_users = 1
    new_site_doc.user_details = []
    new_site_doc.append(
        "user_details",
        {
            "first_name": fname,
            "last_name": lname,
            "user_type": "System User",
            "active": 1,
            "email_id": email,
            "last_active": "",
        },
    )
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


def insert_backup_record(site, backup_path, backup_size, encrypt_backup, frequency):
    try:
        doc = frappe.new_doc("SaaS Sites Backup")
        doc.created_on = frappe_utils.now()
        doc.frequency = frequency
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
    frappe_utils.execute_in_shell(command)


@frappe.whitelist()
def delete_old_backups(site_name, limit, frequency):
    frappe.only_for("System Manager")
    records = frappe.get_list(
        "SaaS Sites Backup",
        filters={"site": site_name, "frequency": frequency},
        fields=["name", "path", "created_on"],
        order_by="created_on desc",
        ignore_permissions=True,
    )
    for i in range(int(limit), len(records)):
        frappe.delete_doc("SaaS Sites Backup", records[i].name)
        frappe.db.commit()
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


@frappe.whitelist()
def reignore_ips():
    f2b.reapply_ignore_ips_from_file()


def update_invoice_due(site_name, due_date):
    commands = [
        "bench --site {} set-config invoice_due_date {}".format(site_name, due_date)
    ]
    execute_commands(commands)


def get_subscription_expiry_grace_days():
    grace_days = frappe.get_doc("SaaS Settings").subscription_expiry_grace_days
    return int(grace_days if grace_days is not None else 5)


def get_site_expiry_date(base_date):
    if not base_date or base_date == "None":
        return None

    return frappe_utils.add_days(
        frappe_utils.getdate(base_date), get_subscription_expiry_grace_days()
    )


def get_site_expiry_base_date(
    subscription_status,
    subscription_starts_on,
    subscription_ends_on,
    invoice_due_date=None,
):
    if invoice_due_date == "None":
        invoice_due_date = None

    if subscription_status in {"past_due", "unpaid"}:
        return invoice_due_date or subscription_starts_on or subscription_ends_on

    return subscription_ends_on


def update_site_expiry_date(site_name, site_expiry_date):
    commands = [
        "bench --site {} set-config site_expiry_date {}".format(
            site_name, site_expiry_date
        )
    ]
    execute_commands(commands)


def update_skip_subscription_expiry(site_name, skip_subscription_expiry):
    commands = [
        "bench --site {} set-config skip_subscription_expiry {}".format(
            site_name, 1 if skip_subscription_expiry else 0
        )
    ]
    execute_commands(commands)


class SaaSSites(Document):
    def __init__(self, *args, **kwargs):
        super(SaaSSites, self).__init__(*args, **kwargs)
        self.site_config = {}
        if hasattr(self, "site_name") and self.site_name:
            site_path = os.path.join(
                frappe_utils.get_bench_path(), "sites", self.site_name
            )
            config_file = os.path.join(site_path, "site_config.json")

            if os.path.exists(config_file):
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
        return frappe.get_site_config(site_path=self.site_name).get(
            "subscription_starts_on"
        )

    @property
    def subscription_ends_on(self):
        return frappe.get_site_config(site_path=self.site_name).get(
            "subscription_ends_on"
        )

    @property
    def invoice_due_date(self):
        return frappe.get_site_config(site_path=self.site_name).get("invoice_due_date")

    @property
    def site_expiry_date(self):
        return frappe.get_site_config(site_path=self.site_name).get("site_expiry_date")

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
        return frappe.get_site_config(site_path=self.site_name).get(
            "subscription_status"
        )

    @property
    def custom_domains(self):
        domains = frappe.get_site_config(site_path=self.site_name).get("domains", [])
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

    def update_ips(self):
        old_doc = self.get_doc_before_save()
        old_ips = old_doc.parse_ips() if old_doc else []
        new_ips = self.parse_ips()

        if not self.whitelist_ips:
            all_ips = list(set(old_ips) | set(new_ips))
            f2b.remove_ignore_ips(all_ips)
        elif not old_doc.whitelist_ips:
            f2b.set_ignore_ips(new_ips)
        else:
            removed_ips = list(set(old_ips) - set(new_ips))
            added_ips = list(set(new_ips) - set(old_ips))

            if removed_ips:
                f2b.remove_ignore_ips(removed_ips)
            if added_ips:
                f2b.set_ignore_ips(added_ips)

    def update_invoice_due(self):
        due_date = None
        for invoice in self.invoices:
            if invoice.due_date and invoice.status in {"open", "uncollectible"}:
                if not due_date:
                    due_date = invoice.due_date
                elif invoice.due_date < due_date:
                    due_date = invoice.due_date

        update_invoice_due(self.site_name, due_date)
        expiry_base_date = get_site_expiry_base_date(
            self.subscription_status,
            self.subscription_starts_on,
            self.subscription_ends_on,
            due_date,
        )
        update_site_expiry_date(self.site_name, get_site_expiry_date(expiry_base_date))

    def on_update(self):
        self.update_ips()
        self.update_invoice_due()
        update_skip_subscription_expiry(self.site_name, self.is_internal_site)
        try:
            self.notify_invoice_update()
        except Exception:
            frappe.log_error(
                "Failed to notify customer about invoice update",
                frappe.get_traceback(),
            )
            frappe.msgprint("Failed to notify customer about invoice update.")

    def on_trash(self):
        if self.whitelist_ips:
            f2b.remove_ignore_ips(self.parse_ips())

    def parse_ips(self, ip_text=None):
        ip_text = ip_text or self.ip_addresses or ""
        raw_ips = re.split(r"[\s,]+", ip_text.strip())

        valid_ips = []
        for ip in raw_ips:
            ip = ip.strip()
            if not ip:
                continue
            try:
                ipaddress.ip_network(ip, strict=False)
                valid_ips.append(ip)
            except ValueError:
                frappe.throw(f"Invalid IP address: {ip}")

        return valid_ips

    def notify_invoice_update(self):
        if self.is_internal_site:
            return

        if len(self.invoices):
            invoice_doc = self.invoices[0]
            saas_settings = frappe.get_doc("SaaS Settings")

            if (
                invoice_doc.status == "uncollectible"
                and not invoice_doc.uncollectible_notified
                and saas_settings.notify_uncollectible_invoice
            ):
                payment_page_url = invoice_doc.payment_page_url
                payment_link = (
                    '<a href="{0}" style="color: #007ee5;">{0}</a>'.format(
                        escape(payment_page_url)
                    )
                    if payment_page_url
                    else ""
                )
                payment_sentence = (
                    "Please complete your payment using this link:"
                    "<br />"
                    "{payment_link}"
                    "<br /><br />"
                    if payment_link
                    else ""
                )
                content = Markup(
                    "We were unable to collect payment for your OneHash subscription on {site_name}. "
                    "Please review your payment method and complete the pending payment "
                    "to avoid any interruption to your service."
                    "<br /><br />"
                    "{payment_sentence}"
                    "If you have already taken action, please ignore this email."
                ).format(
                    payment_sentence=Markup(payment_sentence).format(
                        payment_link=Markup(payment_link)
                    ),
                    site_name=escape(self.site_name),
                )

                utils.send_account_status_email(
                    self.linked_email,
                    content,
                    subject="Payment Failed for Your OneHash Subscription",
                    bcc=utils.parse_email_list(
                        saas_settings.uncollectible_invoice_notification_bcc
                    ),
                )
                frappe.db.set_value(
                    invoice_doc.doctype,
                    invoice_doc.name,
                    "uncollectible_notified",
                    1,
                    update_modified=False,
                )
