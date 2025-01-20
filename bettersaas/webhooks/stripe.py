import frappe
import stripe
from datetime import datetime
from bettersaas.bettersaas.doctype.saas_sites.saas_sites import execute_commands

def get_plan_name(product_id):
    if frappe.conf.get("stripe_prices",{}).get("US", {}).get("products",{}).get("ONEHASH_CRM",{})['product_id'] == product_id:
        return "OneHash_CRM"
    elif frappe.conf.get("stripe_prices",{}).get("US", {}).get("products",{}).get("ONEHASH_ERP",{})['product_id'] == product_id:
        return "OneHash_ERP"

def get_site_name_from_customer_id(customer_id):
    customer = stripe.Customer.retrieve(customer_id)
    site_name = customer.metadata.get("site_name")
    return site_name

def process_subscription_updated(data):
    customer_id = data["customer"]
    metadata = data.get("metadata", {})
    site_name = metadata.get("site_name", "")
    if not site_name:
        site_name = get_site_name_from_customer_id(customer_id)
    subscription_id = data["id"]
    price_id = data["plan"]["id"]
    product_id = data["plan"]["product"]
    plan_name = get_plan_name(data["plan"]["product"])
    quantity = data["quantity"]
    subscription_status = data["status"]
    subscription_starts_on = datetime.fromtimestamp(data["current_period_start"]).date()
    subscription_ends_on = datetime.fromtimestamp(data["current_period_end"]).date()
    commands = []
    commands.append(
        "bench --site {} set-config customer_id {}".format(
            site_name, customer_id
        )
    )
    commands.append(
        "bench --site {} set-config subscription_id {}".format(
            site_name, subscription_id
        )
    )
    commands.append(
        "bench --site {} set-config price_id {}".format(
            site_name, price_id
        )
    )
    commands.append(
        "bench --site {} set-config product_id {}".format(
            site_name, product_id
        )
    )
    commands.append(
        "bench --site {} set-config plan_name {}".format(
            site_name, plan_name
        )
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
    execute_commands(commands)

def process_subscription_deleted(data):
    customer_id = data["customer"]
    metadata = data.get("metadata", {})
    site_name = metadata.get("site_name", "")
    if not site_name:
        site_name = get_site_name_from_customer_id(customer_id)
    subscription_id = data["id"]
    price_id = data["plan"]["id"]
    product_id = data["plan"]["product"]
    plan_name = get_plan_name(data["plan"]["product"])
    quantity = data["quantity"]
    subscription_status = data["status"]
    subscription_starts_on = datetime.fromtimestamp(data["current_period_start"]).date()
    subscription_ends_on = datetime.fromtimestamp(data["current_period_end"]).date()
    commands = []
    commands.append(
        "bench --site {} set-config customer_id {}".format(
            site_name, customer_id
        )
    )
    commands.append(
        "bench --site {} set-config subscription_id {}".format(
            site_name, subscription_id
        )
    )
    commands.append(
        "bench --site {} set-config price_id {}".format(
            site_name, price_id
        )
    )
    commands.append(
        "bench --site {} set-config product_id {}".format(
            site_name, product_id
        )
    )
    commands.append(
        "bench --site {} set-config plan_name {}".format(
            site_name, plan_name
        )
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
    execute_commands(commands)

@frappe.whitelist(allow_guest=True)
def process_payload(*args, **kwargs):
    stripe.api_key = frappe.conf.stripe_secret_key
    stripe.api_version = frappe.conf.stripe_api_version
    endpoint_secret = frappe.conf.stripe_endpoint_secret
    payload = frappe.local.request.data
    sig_header = frappe.local.request.headers['Stripe-Signature']
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        raise e
    except stripe.error.SignatureVerificationError as e:
        raise e
    
    if event['type'] == 'customer.subscription.created':
        process_subscription_updated(event.data.object)
    elif event['type'] == 'customer.subscription.updated':
        process_subscription_updated(event.data.object)
    elif event['type'] == 'customer.subscription.deleted':
        process_subscription_deleted(event.data.object)
    else:
        print('Unhandled event type {}'.format(event.type))

    frappe.response["status"] = 200 