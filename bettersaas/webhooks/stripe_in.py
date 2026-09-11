import frappe
import stripe

from bettersaas.webhooks.stripe_service import (
    process_invoice_update,
    process_subscription_deleted,
    process_subscription_updated,
)


def get_plan_name(data):
    product_id = data["plan"]["product"]
    if (
        frappe.conf.get("stripe_prices", {})
        .get("IN", {})
        .get("products", {})
        .get("ONEHASH_CRM", {})["product_id"]
        == product_id
    ):
        return "OneHash_CRM"
    elif (
        frappe.conf.get("stripe_prices", {})
        .get("IN", {})
        .get("products", {})
        .get("ONEHASH_ERP", {})["product_id"]
        == product_id
    ):
        return "OneHash_ERP"


@frappe.whitelist(allow_guest=True)
def process_payload(*args, **kwargs):
    stripe.api_key = frappe.conf.stripe_secret_key_in
    stripe.api_version = frappe.conf.stripe_api_version
    endpoint_secret = frappe.conf.stripe_endpoint_secret_in
    payload = frappe.local.request.data
    sig_header = frappe.local.request.headers["Stripe-Signature"]
    event = None
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        raise e
    except stripe.error.SignatureVerificationError as e:
        raise e

    if event["type"] in {
        "customer.subscription.created",
        "customer.subscription.updated",
    }:
        process_subscription_updated(
            event.data.object,
            get_plan_name(event.data.object),
            event_created=event.get("created"),
        )
    elif event["type"] == "customer.subscription.deleted":
        process_subscription_deleted(
            event.data.object,
            get_plan_name(event.data.object),
            event_created=event.get("created"),
        )
    elif event["type"] in {
        "invoice.finalized",
        "invoice.paid",
        "invoice.marked_uncollectible",
        "invoice.overdue",
    }:
        process_invoice_update(event.data.object)
    else:
        print("Unhandled event type {}".format(event.type))

    frappe.response["status"] = 200
