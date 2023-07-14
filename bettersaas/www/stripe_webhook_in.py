import frappe
import json
import stripe
from whitelabel.api import StripeSubscriptionManager
stripe_manager = StripeSubscriptionManager(country="IN")


    
@frappe.whitelist(allow_guest=True)
def handler(*args, **kwargs):
    payload = frappe.local.request.get_data()
    sig_header = frappe.local.request.headers['Stripe-Signature']
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_manager.endpoint_secret
        )
    except ValueError as e:
        print("invalid payload")
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print("invalid signature")
        raise e
    print("event type", event["type"])
    if event["type"] == "checkout.session.completed":
        stripe_manager.handle_checkout_session_completed(event)
        
    if event["type"] == "invoice.paid":
        stripe_manager.handle_invoice_paid(event)
    if event["type"] == "invoice.payment_action_required":
        # get invoice client secret
        stripe_manager.handle_payment_intent_action_required(event)
    if event["type"] =="payment_intent.payment_failed":
        stripe_manager.handle_payment_intent_failed(event)


    

def fulfilOneHashUpdate(product_id,price_id,site_name):
    # pass the checkout session 
    if product_id in stripe_manager.onehas_subscription_product_ids:
            # handle onehash subscription
        product = stripe.Product.retrieve(product_id)
        user_limit = 10
        plan_name = ""
        if product.name == "OneHash Pro":
                user_limit = 100000
                plan_name = "ONEHASH_PRO"   
        elif product.name == "OneHash Starter":
                user_limit = 10
                plan_name = "ONEHASH_STARTER"
        else :
                user_limit = 30
                plan_name = "ONEHASH_PLUS"
        command_to_set_limit = "bench --site {site_name} set-config  max_users {user_limit}".format(site_name=site_name,user_limit=user_limit)
        command_to_set_plan = "bench --site {site_name} set-config  plan {plan}".format(site_name=site_name,plan=plan_name)
        command_to_set_price_id = "bench --site {site_name} set-config  price_id {price_id}".format(site_name=site_name,price_id=price_id)
        frappe.utils.execute_in_shell(command_to_set_limit)
        frappe.utils.execute_in_shell(command_to_set_plan)
        frappe.utils.execute_in_shell(command_to_set_price_id)
    

def test():
    import stripe
    stripe.api_key = frappe.conf.STRIPE_SECRET_KEY
    cust = stripe.Customer.create(
        email="test@test2.com",
        name="test",
        stripe_account="acct_1Hf3MFCwmuPVDwVy",
    )