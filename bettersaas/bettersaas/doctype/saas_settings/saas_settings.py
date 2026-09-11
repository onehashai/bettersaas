# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import os
import shlex
import frappe
import shutil
import traceback
from datetime import datetime, timedelta
from frappe.utils.password import decrypt
from frappe.model.document import Document
from markupsafe import Markup, escape
from bettersaas.bettersaas.utils import parse_email_list, send_account_status_email


def get_days_since_creation(folder_path):
    try:
        creation_time = os.path.getctime(folder_path)
        creation_date = datetime.fromtimestamp(creation_time)
        days_since_creation = (datetime.now() - creation_date).days
        return days_since_creation
    except Exception as e:
        return f"An error occurred: {e}"


@frappe.whitelist()
def delete_archived_sites():
    from frappe.utils import get_bench_path

    conf = frappe.get_doc("SaaS Settings")
    if not conf.arch_site_delete_conf_enabled:
        return
    directory_path = os.path.join(get_bench_path(), "archived", "sites")
    threshold_days = conf.threshold_days
    try:
        for folder_name in os.listdir(directory_path):
            folder_path = os.path.join(directory_path, folder_name)
            if os.path.isdir(folder_path):
                days_since_creation = get_days_since_creation(folder_path)
                if (
                    isinstance(days_since_creation, int)
                    and days_since_creation > threshold_days
                ):
                    shutil.rmtree(folder_path)
    except Exception as e:
        frappe.msgprint(f"An error occurred: {e}")


def get_last_login_date(site_name):
    from frappe.frappeclient import FrappeClient

    site = frappe.db.get("SaaS Sites", filters={"site_name": site_name})
    site_password = decrypt(site.encrypted_password, frappe.conf.encryption_key)
    conn = FrappeClient("http://" + site_name, "Administrator", site_password)
    active_users_last_active = conn.get_list(
        "User",
        fields=["last_active"],
        filters={"enabled": "1", "name": ["!=", "Administrator"]},
        limit_page_length=10000,
    )
    latest_last_active = max(
        (
            datetime.fromisoformat(user["last_active"])
            for user in active_users_last_active
            if user["last_active"]
        ),
        default=None,
    )
    return latest_last_active


@frappe.whitelist()
def delete_free_sites():
    saas_settings = frappe.get_doc("SaaS Settings")
    if not saas_settings.site_delete_conf_enabled:
        return
    sites = frappe.get_list(
        "SaaS Sites",
        fields=["site_name"],
        filters={"status": "Active", "is_internal_site": 0},
    )
    to_be_deleted = []
    for site in sites:
        try:
            site_config = frappe.get_site_config(site_path=site.site_name)
            expiry_date = frappe.utils.getdate(
                site_config.get("invoice_due_date")
                or site_config.get("subscription_ends_on")
            )

            if site_config.get("subscription_status") == "active":
                pass
            elif (
                site_config.get("subscription_status") == "trialing"
                and expiry_date > frappe.utils.getdate()
            ):
                pass
            else:
                to_be_deleted.append(site)
        except:
            pass
    failed_to_delete = []
    for site in to_be_deleted:
        try:
            site_config = frappe.get_site_config(site_path=site.site_name)
            linked_email = site_config.customer_email

            last_login_date = get_last_login_date(site.site_name)
            present_date = datetime.now()
            inactive_days = saas_settings.inactive_for_days
            if last_login_date is not None:
                inactive_days = (present_date - last_login_date).days
            days_until_deletion = saas_settings.inactive_for_days - inactive_days
            exp_date = present_date + timedelta(days=days_until_deletion)
            if inactive_days >= saas_settings.inactive_for_days:
                content = "This is to notify you that on {exp_date}, your OneHash account {site_name} with email address {email_address} been permanently terminated. You won't be able to retrieve any data or access your account any more.".format(
                    email_address=linked_email,
                    exp_date=exp_date.strftime("%d-%m-%y"),
                    site_name=site.site_name,
                )
                send_account_status_email(linked_email, content)
                method = "bettersaas.api.delete_site"
                frappe.enqueue(method, queue="short", site_name=site.site_name)
            elif (
                inactive_days
                >= saas_settings.inactive_for_days - saas_settings.warning_days
            ):
                content = "This is to let you know that on {exp_date}, your OneHash account {site_name} with email address {email_address} will be permanently removed. You will no longer be able to retrieve any data or access your account".format(
                    email_address=linked_email,
                    exp_date=exp_date.strftime("%d-%m-%y"),
                    site_name=site.site_name,
                )
                send_account_status_email(linked_email, content)
            elif (
                inactive_days
                >= saas_settings.inactive_for_days
                - saas_settings.intermittent_warning_days
            ):
                content = "This is to let you know that on {exp_date}, your OneHash account {site_name} with email address {email_address} will be permanently removed. You will no longer be able to retrieve any data or access your account.".format(
                    email_address=linked_email,
                    exp_date=exp_date.strftime("%d-%m-%y"),
                    site_name=site.site_name,
                )
                send_account_status_email(linked_email, content)
        except Exception:
            failed_to_delete.append(
                {"site": site.site_name, "error": traceback.format_exc()}
            )

    if failed_to_delete:
        frappe.log_error("Failed to delete sites", failed_to_delete)
    return "success"


@frappe.whitelist()
def update_refresh_stock_site_scheduler(check_every):
    check_every = int(check_every)
    hours = check_every // 3600
    remaining_seconds = check_every % 3600
    minutes = remaining_seconds // 60

    if check_every < 60:
        frappe.throw(
            f"Invalid check_every value: {check_every}. Must be at least 60 seconds."
        )

    if minutes == 0 and hours != 0:
        cron_expression = f"0 */{hours} * * *"

    elif hours == 0 and minutes != 0:
        cron_expression = f"*/{minutes} * * * *"

    else:
        cron_expression = f"{minutes} */{hours} * * *"

    job = frappe.get_doc("Scheduled Job Type", "saas_stock_sites.refresh_stock_sites")
    job.cron_format = cron_expression
    job.save()


@frappe.whitelist(allow_guest=True)
def get_backup_limit(frequency):
    if frequency == "Daily":
        return frappe.get_doc("SaaS Settings").daily
    elif frequency == "Alternate Days":
        return frappe.get_doc("SaaS Settings").alternate_days
    elif frequency == "Weekly":
        return frappe.get_doc("SaaS Settings").weekly
    elif frequency == "Monthly":
        return frappe.get_doc("SaaS Settings").monthly


def parse_site_expiry_notification_days(notification_days):
    days = set()
    for value in (notification_days or "").split(","):
        value = value.strip()
        if not value:
            continue
        try:
            days.add(int(value))
        except ValueError:
            frappe.log_error(
                "Invalid site expiry notification day",
                f"Could not parse '{value}' from '{notification_days}'",
            )
    return days


def get_config_date(site_config, key):
    value = site_config.get(key)
    if value and value != "None":
        return frappe.utils.getdate(value)


def get_payment_page_url(site):
    invoices = [
        invoice
        for invoice in site.invoices
        if invoice.payment_page_url and invoice.status in {"open", "uncollectible"}
    ]
    invoices.sort(key=lambda invoice: invoice.due_date or frappe.utils.getdate())
    if invoices:
        return invoices[0].payment_page_url


def get_site_expiry_reminder_content(site_name, expiry_date, payment_page_url=None):
    payment_sentence = (
        "Please complete your payment using this link:"
        "<br />"
        "{payment_link}"
        "<br /><br />"
        if payment_page_url
        else ""
    )
    payment_link = (
        '<a href="{0}" style="color: #007ee5;">{0}</a>'.format(escape(payment_page_url))
        if payment_page_url
        else ""
    )

    return Markup(
        "This is a reminder that your OneHash account {site_name} will expire "
        "on {expiry_date}."
        "<br /><br />"
        "Please renew your subscription before this date to continue using your "
        "services without interruption."
        "<br /><br />"
        "{payment_sentence}"
        "If you have already renewed or have auto renewal set up, please ignore "
        "this email."
    ).format(
        site_name=escape(site_name),
        expiry_date=escape(expiry_date.strftime("%d %B %Y")),
        payment_sentence=Markup(payment_sentence).format(
            payment_link=Markup(payment_link)
        ),
    )


def notify_site_expiration():
    saas_settings = frappe.get_doc("SaaS Settings")
    if not saas_settings.notify_for_site_expiry:
        return

    notification_days = parse_site_expiry_notification_days(
        saas_settings.site_expiry_notification_days
    )
    if not notification_days:
        return

    today = frappe.utils.getdate()
    sites = frappe.get_all(
        "SaaS Sites",
        fields=["name", "site_name", "linked_email"],
        filters={"status": "Active", "is_internal_site": 0},
    )

    failed_to_notify = []
    for site in sites:
        try:
            site_config = frappe.get_site_config(site_path=site.site_name)
            expiry_date = get_config_date(site_config, "site_expiry_date")
            if not expiry_date:
                continue

            days_until_expiry = (expiry_date - today).days
            if days_until_expiry not in notification_days:
                continue

            recipient = site.linked_email or site_config.get("customer_email")
            if not recipient:
                continue

            site_doc = frappe.get_doc("SaaS Sites", site.name)
            content = get_site_expiry_reminder_content(
                site.site_name, expiry_date, get_payment_page_url(site_doc)
            )
            send_account_status_email(
                recipient,
                content,
                subject="OneHash Account Expiration Reminder",
                bcc=parse_email_list(saas_settings.site_expiry_notification_bcc),
            )
        except Exception:
            failed_to_notify.append(
                {"site": site.site_name, "error": traceback.format_exc()}
            )

    if failed_to_notify:
        frappe.log_error("Failed to notify site expiration", failed_to_notify)


class SaaSSettings(Document):
    def on_update(self):
        old_doc = self.get_doc_before_save()
        if old_doc and (
            old_doc.subscription_expiry_grace_days
            == self.subscription_expiry_grace_days
        ):
            return

        frappe.enqueue_doc(
            self.doctype,
            self.name,
            "refresh_site_expiry_dates",
            queue="long",
            timeout=3600,
            enqueue_after_commit=True,
        )

    def refresh_site_expiry_dates(self):
        from bettersaas.bettersaas.doctype.saas_sites.saas_sites import (
            execute_commands,
            get_subscription_expiry_grace_days,
            get_site_expiry_base_date,
            get_site_expiry_date,
        )

        grace_days = get_subscription_expiry_grace_days()
        sites_path = os.path.realpath(
            os.path.join(frappe.utils.get_bench_path(), "sites")
        )
        commands = []
        missing_site_configs = []
        for site_name in frappe.get_all("SaaS Sites", pluck="site_name"):
            site_path = os.path.realpath(os.path.join(sites_path, site_name))
            site_config_path = os.path.join(site_path, "site_config.json")
            if (
                os.path.commonpath([sites_path, site_path]) != sites_path
                or not os.path.isfile(site_config_path)
            ):
                missing_site_configs.append(site_name)
                continue

            site_config = frappe.get_site_config(site_path=site_name)
            expiry_base_date = get_site_expiry_base_date(
                site_config.get("subscription_status"),
                site_config.get("subscription_starts_on"),
                site_config.get("subscription_ends_on"),
                site_config.get("invoice_due_date"),
            )
            commands.append(
                "bench --site {} set-config subscription_expiry_grace_days {}".format(
                    shlex.quote(str(site_name)),
                    shlex.quote(str(grace_days)),
                )
            )
            commands.append(
                "bench --site {} set-config site_expiry_date {}".format(
                    shlex.quote(str(site_name)),
                    shlex.quote(str(get_site_expiry_date(expiry_base_date))),
                )
            )

        if missing_site_configs:
            frappe.log_error(
                title="Skipped subscription expiry refresh for missing sites",
                message="\n".join(missing_site_configs),
            )

        if commands:
            execute_commands(commands)
