

# import json
# import os
# import stripe
# import frappe

# # The library needs to be configured with your account's secret key.
# # Ensure the key is kept out of any version control system you might be using.
# stripe.api_key = "sk_test_..."

# # This is your Stripe CLI webhook secret for testing your endpoint locally.
# endpoint_secret = 'whsec_eda93bf372ba5a19f4ca1c1dc9b076566a44d700f1a0f35a1d7ac47f5d929fa7'


# @frappe.whitelist(allow_guest=True,methods=['POST'])
# def webhook(*args, **kwargs):
#     print("webhook called")
#     return "hi"
#     # event = None
#     # payload = kwargs["payload"]
#     # sig_header = frappe.local.requst.headers['STRIPE_SIGNATURE']

#     # try:
#     #     event = stripe.Webhook.construct_event(
#     #         payload, sig_header, endpoint_secret
#     #     )
#     # except ValueError as e:
#     #     print("invalid payload")
#     #     # Invalid payload
#     #     raise e
#     # except stripe.error.SignatureVerificationError as e:
#     #     # Invalid signature
#     #     print("invalid signature")
#     #     raise e

#     # # Handle the event
#     # if event['type'] == 'payment_intent.succeeded':
#     #   payment_intent = event['data']['object']
#     # # ... handle other event types
#     # else:
#     #   print('Unhandled event type {}'.format(event['type']))

#     # return "success"