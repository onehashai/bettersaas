import os
import shlex
from datetime import datetime

import frappe
import stripe
from filelock import FileLock
from frappe.utils import get_bench_path

from bettersaas.bettersaas.doctype.saas_sites.saas_sites import (
    execute_commands,
    get_subscription_expiry_grace_days,
    get_site_expiry_base_date,
    get_site_expiry_date,
)


def get_site_name_from_customer_id(customer_id):
    customer = stripe.Customer.retrieve(customer_id)
    site_name = customer.get("metadata", {}).get("site_name")
    return site_name


def get_date_from_timestamp(timestamp):
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp).date()


def get_current_invoice_due_date(site_name):
    invoice_due_date = frappe.get_site_config(site_path=site_name).get(
        "invoice_due_date"
    )
    if invoice_due_date and invoice_due_date != "None":
        return invoice_due_date


def get_subscription_sync_lock(site_name):
    sites_path = os.path.realpath(os.path.join(get_bench_path(), "sites"))
    site_path = os.path.realpath(os.path.join(sites_path, site_name))
    if os.path.commonpath([sites_path, site_path]) != sites_path:
        frappe.throw("Invalid site name in Stripe subscription metadata")

    if not os.path.isfile(os.path.join(site_path, "site_config.json")):
        frappe.throw(f"Site config not found for {site_name}")

    return FileLock(
        os.path.join(site_path, "locks", "stripe_subscription_sync.lock"), timeout=30
    )


def get_set_config_command(site_name, key, value):
    return "bench --site {} set-config {} {}".format(
        shlex.quote(str(site_name)), shlex.quote(str(key)), shlex.quote(str(value))
    )


def process_subscription_updated(data, plan_name, event_created=None):
    sync_subscription(data, plan_name, event_created)


def process_subscription_deleted(data, plan_name, event_created=None):
    sync_subscription(data, plan_name, event_created)


def sync_subscription(data, plan_name, event_created=None):
    customer_id = data["customer"]
    metadata = data.get("metadata", {})
    site_name = metadata.get("site_name", "") or get_site_name_from_customer_id(
        customer_id
    )
    if not site_name:
        return
    sync_subscription_by_id(data["id"], site_name, plan_name, event_created)


def sync_subscription_by_id(subscription_id, site_name, plan_name, event_created=None):
    with get_subscription_sync_lock(site_name):
        site_config = frappe.get_site_config(site_path=site_name)
        last_event_created = site_config.get("stripe_subscription_event_created")
        if (
            event_created is not None
            and last_event_created is not None
            and int(event_created) < int(last_event_created)
        ):
            return

        # Stripe doesn't guarantee webhook delivery order. Always retrieve the current
        # object while holding the per-site lock instead of applying an event snapshot.
        current_data = stripe.Subscription.retrieve(subscription_id)
        update_subscription_config(
            current_data, plan_name, site_name, event_created=event_created
        )


def update_subscription_config(data, plan_name, site_name, event_created=None):
    customer_id = data["customer"]
    subscription_id = data["id"]
    price_id = data["plan"]["id"]
    product_id = data["plan"]["product"]
    quantity = data["quantity"]
    subscription_status = data["status"]
    subscription_starts_on = get_date_from_timestamp(data["current_period_start"])
    subscription_ends_on = get_date_from_timestamp(data["current_period_end"])
    expiry_base_date = get_site_expiry_base_date(
        subscription_status,
        subscription_starts_on,
        subscription_ends_on,
        get_current_invoice_due_date(site_name),
    )
    values = {
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "price_id": price_id,
        "product_id": product_id,
        "plan_name": plan_name,
        "subscription_quantity": quantity,
        "subscription_status": subscription_status,
        "subscription_starts_on": subscription_starts_on,
        "subscription_ends_on": subscription_ends_on,
        "subscription_expiry_grace_days": get_subscription_expiry_grace_days(),
        "site_expiry_date": get_site_expiry_date(expiry_base_date),
    }
    if event_created is not None:
        values["stripe_subscription_event_created"] = event_created

    site_config = frappe.get_site_config(site_path=site_name)
    commands = [
        get_set_config_command(site_name, key, value)
        for key, value in values.items()
        if str(site_config.get(key)) != str(value)
    ]
    if commands:
        execute_commands(commands)


def process_invoice_update(data):
    if data["object"] != "invoice":
        return

    customer_id = data["customer"]
    if isinstance(customer_id, dict):
        customer_id = customer_id["id"]
    metadata = data.get("metadata", {})

    site_name = metadata.get("site_name", "")
    if not site_name:
        site_name = get_site_name_from_customer_id(customer_id)

    if site_name and frappe.db.exists("SaaS Sites", site_name):
        site_doc = frappe.get_doc("SaaS Sites", site_name)

        invoice_id = data["id"]
        status = data["status"]
        due_date = get_date_from_timestamp(data["due_date"])
        paid_at = get_date_from_timestamp(data["status_transitions"]["paid_at"])
        payment_url = data.get("hosted_invoice_url")

        invoice_doc_data = {
            "invoice_id": invoice_id,
            "status": status,
            "due_date": due_date,
            "paid_on": paid_at,
            "payment_page_url": payment_url,
        }

        invoice_found = False
        for invoice in site_doc.invoices:
            if invoice.invoice_id == invoice_id:
                invoice.update(invoice_doc_data)
                invoice_found = True
                break

        if not invoice_found:
            site_doc.append("invoices", invoice_doc_data, 0)

        site_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Invoice and subscription webhooks can arrive out of order. Re-read the
        # site's current Stripe subscription after every relevant invoice change so
        # paid/uncollectible recovery cannot leave a stale subscription status.
        site_config = frappe.get_site_config(site_path=site_name)
        subscription_id = site_config.get("subscription_id")
        if subscription_id:
            sync_subscription_by_id(
                subscription_id,
                site_name,
                site_config.get("plan_name"),
            )
