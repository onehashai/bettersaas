import frappe
import stripe
from datetime import datetime
from bettersaas.bettersaas.doctype.saas_sites.saas_sites import (
    execute_commands,
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


def process_subscription_updated(data, plan_name):
    customer_id = data["customer"]
    metadata = data.get("metadata", {})
    site_name = metadata.get("site_name", "") or get_site_name_from_customer_id(
        customer_id
    )
    if not site_name:
        return
    subscription_id = data["id"]
    price_id = data["plan"]["id"]
    product_id = data["plan"]["product"]
    quantity = data["quantity"]
    subscription_status = data["status"]
    subscription_starts_on = get_date_from_timestamp(data["current_period_start"])
    subscription_ends_on = get_date_from_timestamp(data["current_period_end"])
    commands = []
    commands.append(
        "bench --site {} set-config customer_id {}".format(site_name, customer_id)
    )
    commands.append(
        "bench --site {} set-config subscription_id {}".format(
            site_name, subscription_id
        )
    )
    commands.append(
        "bench --site {} set-config price_id {}".format(site_name, price_id)
    )
    commands.append(
        "bench --site {} set-config product_id {}".format(site_name, product_id)
    )
    commands.append(
        "bench --site {} set-config plan_name {}".format(site_name, plan_name)
    )
    commands.append(
        "bench --site {} set-config subscription_quantity {}".format(
            site_name, quantity
        )
    )
    commands.append(
        "bench --site {} set-config subscription_status {}".format(
            site_name, subscription_status
        )
    )
    commands.append(
        "bench --site {} set-config subscription_starts_on {}".format(
            site_name, subscription_starts_on
        )
    )
    commands.append(
        "bench --site {} set-config subscription_ends_on {}".format(
            site_name, subscription_ends_on
        )
    )
    commands.append(
        "bench --site {} set-config site_expiry_date {}".format(
            site_name,
            get_site_expiry_date(
                get_current_invoice_due_date(site_name) or subscription_ends_on
            ),
        )
    )
    execute_commands(commands)


def process_subscription_deleted(data, plan_name):
    customer_id = data["customer"]
    metadata = data.get("metadata", {})
    site_name = metadata.get("site_name", "") or get_site_name_from_customer_id(
        customer_id
    )
    if not site_name:
        return
    subscription_id = data["id"]
    price_id = data["plan"]["id"]
    product_id = data["plan"]["product"]
    quantity = data["quantity"]
    subscription_status = data["status"]
    subscription_starts_on = get_date_from_timestamp(data["current_period_start"])
    subscription_ends_on = get_date_from_timestamp(data["current_period_end"])
    commands = []
    commands.append(
        "bench --site {} set-config customer_id {}".format(site_name, customer_id)
    )
    commands.append(
        "bench --site {} set-config subscription_id {}".format(
            site_name, subscription_id
        )
    )
    commands.append(
        "bench --site {} set-config price_id {}".format(site_name, price_id)
    )
    commands.append(
        "bench --site {} set-config product_id {}".format(site_name, product_id)
    )
    commands.append(
        "bench --site {} set-config plan_name {}".format(site_name, plan_name)
    )
    commands.append(
        "bench --site {} set-config subscription_quantity {}".format(
            site_name, quantity
        )
    )
    commands.append(
        "bench --site {} set-config subscription_status {}".format(
            site_name, subscription_status
        )
    )
    commands.append(
        "bench --site {} set-config subscription_starts_on {}".format(
            site_name, subscription_starts_on
        )
    )
    commands.append(
        "bench --site {} set-config subscription_ends_on {}".format(
            site_name, subscription_ends_on
        )
    )
    commands.append(
        "bench --site {} set-config site_expiry_date {}".format(
            site_name,
            get_site_expiry_date(
                get_current_invoice_due_date(site_name) or subscription_ends_on
            ),
        )
    )
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
