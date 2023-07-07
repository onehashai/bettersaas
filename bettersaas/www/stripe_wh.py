import frappe
import sys
import json
from bettersaas.bettersaas.api import upgrade_site
import stripe
@frappe.whitelist(allow_guest=True)
def stripe_webhook(*args, **kwargs):
    auth_header = frappe.get_request_header('Authorization')
    event = None
    if(auth_header != frappe.conf.internal_auth_key):
        frappe.throw("Not Authorized")
        return "Not Authorized"
    try:
        event = json.loads(frappe.get_doc("stripe sessions",kwargs["session_id"],fields=["product_json"],ignore_permissions=True).session_json)
    except Exception as e:
        print("error",e)
    stripe.api_key="sk_test_51HIMtgEwPMdYWOILiaLZkneayuzD5xuwumeaC6f3GuOlmpxxh7znRf34Xi37MPk8m7S2U9vns3YYEqilwrorTXsI00xF2ajx2F"
    hanlded_events = ["customer.subscription.created","customer.created"]
    if event["type"]  not in hanlded_events:
        return;
    print(event["type"])
    if event["type"] == "customer.created":
        print(event)
        saas_user = frappe.get_doc("SaaS users",{ "email":event["data"]["object"]["email"]})
        print(saas_user.name)
        saas_user.stripe_cus_id = event["data"]["object"]["id"]
        saas_user.save(ignore_permissions=True)
        print(saas_user.stripe_cus_id)
        frappe.db.commit()
    if event["type"] == "customer.subscription.created":
        subscription_id = event["data"]["object"]["id"]
        product_id = event["data"]["object"]["items"]["data"][0]["price"]["product"]
        print("pID",product_id)
        product = stripe.Product.retrieve(product_id)
        product_metadata = product["metadata"]
        site = frappe.get_last_doc("SaaS users",filters={ "stripe_cus_id":event["data"]["object"]["customer"]}).site
        print(site)
        frappe.utils.execute_in_shell("bench --site {} set-config {} {}".format(site,"plan",product_metadata["product_id"]))
        frappe.utils.execute_in_shell("bench --site {} set-config {} {}".format(site,"max_users",product_metadata["user_count"]))
        # set site expiry date 3 days after next billing date
        expiry_date = frappe.utils.add_days(event["data"]["object"]["current_period_end"],0)
        frappe.utils.execute_in_shell("bench --site {} set-config {} {}".format(site,"expiry_date",expiry_date))
        frappe.utils.execute_in_shell("bench --site {} set-config {} {}".format(site,"stripe_subscription_id",event["data"]["object"]["id"]))
        
    # upgrade_site(product["metadata"],session["client_reference_id"])
    # plan_doc = frappe.new_doc("SaaS site plans")
    # plan_doc.name = session["client_reference_id"] + "." + frappe.get_doc("SaaS settings").domain
    # plan_doc.plan = product["metadata"]["product_id"]
    # plan_doc.metadata = json.dumps(product["metadata"])
    # plan_doc.insert(ignore_permissions=True)
    return "Site limits updated"
    
        


# stripe workflow
# when user creates a site 
# 1. create a stripe customer
# 2. create a stripe subscription with price of Onehash pro
# 

# when user clicks on upgrade
# 1. move to pricing page
# 2. select a plan
# 3. stripe calls webhook with plan id and metadata
# 4. update site limits