# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
import math
import random
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.utils.password import decrypt, encrypt
from clientside.stripe import StripeSubscriptionManager


def generate_otp():
    # Declare a digits variable
    # which stores all digits
    digits = "0123456789"
    OTP = ""
    # length of password can be chaged
    # by changing value in range
    for i in range(6):
        OTP += digits[math.floor(random.random() * 10)]
    return OTP


def send_otp_sms(number, otp):
    receiver_list = []
    receiver_list.append(number)
    message = otp + " is OTP to verify your account request for OneHash."
    send_sms(receiver_list, message, sender_name="", success_msg=False)


def send_otp_email(otp, email):
    STANDARD_USERS = ("Guest", "Administrator")
    subject = "Please confirm this email address for OneHash"
    template = "signup_otp_email"
    args = {
        "first_name": "user",
        "last_name": "",
        "title": subject,
        "otp": otp,
    }
    sender = None
    frappe.sendmail(
        recipients=email,
        sender=sender,
        subject=subject,
        bcc=["anand@onehash.ai"],
        template=template,
        args=args,
        header=[subject, "green"],
        delayed=False,
    )
    return True


def verifyPhoneAndEmailDuplicacy(email, phone):
    if frappe.db.exists("SaaS users", {"email": email}):
        return "EMAIL_EXISTS"
    if frappe.db.exists("SaaS users", {"phone": phone}):
        return "PHONE_EXISTS"
    return "success"


@frappe.whitelist(allow_guest=True)
def send_otp(email, phone):
    # generate random string
    doc = frappe.db.get_all(
        "OTP",
        filters={"email": email},
        fields=["otp", "modified"],
        order_by="modified desc",
    )
    new_otp_doc = frappe.new_doc("OTP")
    if (
        len(doc) > 0
        and frappe.utils.time_diff_in_seconds(
            frappe.utils.now(), doc[0].modified.strftime("%Y-%m-%d %H:%M:%S.%f")
        )
        < 10 * 60
    ):
        new_otp_doc.otp = doc[0].otp

    else:
        print("GENERATING")
        new_otp_doc.otp = generate_otp()

    unique_id = frappe.generate_hash("", 5)

    new_otp_doc.id = unique_id

    new_otp_doc.email = email
    if phone:
        new_otp_doc.phone = phone
        send_otp_sms(phone, new_otp_doc.otp)
    print(new_otp_doc.otp)

    #MrAbhi----------------------------------------------
    ws=frappe.get_doc('Wati Settings')
    token=ws.access_token
    if len(str(phone))==10:
        mno='91'+str(phone)
    else:
        mno=str(phone)
    url = f"https://live-server-5625.wati.io/api/v2/sendTemplateMessage?whatsappNumber={mno}"

    payload = json.dumps({
    "template_name": "otp_signup",
    "broadcast_name": "Broadcast",
    "parameters": [
        {
        "name": "signup_otp",
        "value": new_otp_doc.otp
        }
    ]
    })
    headers = {
    'Content-Type': 'application/json',
    'Authorization': token,
    'Cookie': 'affinity=1691606468.17.170.926313|e8158ed42d7caddb1c06a933867d41fb'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
#----------------------------------------------------------------------------------
    
    send_otp_email(new_otp_doc.otp, email)
    new_otp_doc.save(ignore_permissions=True)
    print(new_otp_doc)
    frappe.db.commit()
    return unique_id


@frappe.whitelist(allow_guest=True)
def verify_account_request(unique_id, otp):
    print("ed", unique_id, otp)
    doc = frappe.db.get_all(
        "OTP", filters={"id": unique_id}, fields=["otp", "modified"]
    )
    print(
        "s",
    )
    if len(doc) == 0:
        return "OTP_NOT_FOUND"
    doc = doc[0]
    if (
        frappe.utils.time_diff_in_seconds(
            frappe.utils.now(), doc.modified.strftime("%Y-%m-%d %H:%M:%S.%f")
        )
        > 600
    ):
        return "OTP_EXPIRED"
    elif doc.otp != otp:
        return "INVALID_OTP"
    frappe.db.commit()
    return "SUCCESS"


@frappe.whitelist()
def create_user(first_name, last_name, email, site, phone):
    user = frappe.new_doc("SaaS users")
    print("creating user with", first_name, last_name, email, site, phone)
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.site = site
    user.phone = phone
    user.save(ignore_permissions=True)
    frappe.db.commit()
    # return user "name"
    
    return user


from frappe.model.document import Document


@frappe.whitelist(allow_guest=True)
def get_sites(email):
    return frappe.get_all(
        "SaaS sites",
        filters={"linked_email": email},
        fields=["name", "site_name"],
    )


@frappe.whitelist(allow_guest=True)
def check_user_name_and_password_for_a_site(site_name, email, password):
    print("checkin")
    site = frappe.db.get_all(
        "SaaS sites",
        filters={"site_name": site_name, "linked_email": email},
        fields=["linked_email", "encrypted_password", "site_name", "cus_id"],
    )
    if len(site) == 0:
        return "INVALID_SITE"

    site = site[0]

    dec_password = decrypt(site.encrypted_password, frappe.conf.enc_key)
    if site:
        if dec_password != password:
            return "INVALID_CREDENTIALS"
    # check for active subscription
    #  print(frappe.conf)
    country = frappe.get_site_config(site_path=site.site_name)["country"]
    stripe_subscription_manager = StripeSubscriptionManager(country=country)
    has_sub = stripe_subscription_manager.has_valid_site_subscription(site.cus_id)
    # find user and check if has role of Administator
    hasRoleAdmin = frappe.db.exists(
        "Has Role", {"parent": email, "role": "Administrator"}
    )
    print(hasRoleAdmin)
    if not has_sub:
        return "NO_SUBSCRIPTION"
    return "OK"


@frappe.whitelist()
def get_all_users_of_a_site():
    site = "Samsun.localhost"
    a = frappe.db.sql(
        "select email from `tabSaaS users` where site = %s", site, as_dict=1
    )
    print(a)


class SaaSusers(Document):
    pass


# 980555
