# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt 

import frappe
import math
import random
import requests
import json
import socket
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.utils.password import decrypt
from frappe.model.document import Document
# from clientside.stripe import StripeSubscriptionManager


def generate_otp():
    digits = "0123456789"
    OTP = ""
    for i in range(6):
        OTP += digits[math.floor(random.random() * 10)]
    return OTP

def send_otp_via_sms(number, otp):
    receiver_list = []
    receiver_list.append(number)
    message = otp + " is OTP to verify your account request for OneHash."
    send_sms(receiver_list, message, sender_name="", success_msg=False)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return f"Error occurred: {e}"

def send_otp_via_email(otp, email):
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
        bcc=[""],
        template=template,
        args=args,
        header=[subject, "green"],
        delayed=False,
    )
    return True

@frappe.whitelist(allow_guest=True)
def send_otp(email, phone, fname, lname, company_name, site_name):
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
        new_otp_doc.otp = generate_otp()

    unique_id = frappe.generate_hash("", 5)
    new_otp_doc.id = unique_id
    new_otp_doc.ip = str(get_ip())
    new_otp_doc.email = email
    if phone and frappe.conf.domain != "localhost":
        new_otp_doc.phone = phone
        from datetime import datetime

        doc_otp=frappe.get_list('OTP',fields=['*'],filters={'ip':str(get_ip()),'date':datetime.now().date()})
        if doc_otp:
            count=0
            for i in doc_otp:
                count+=1
            if count<=2:
                send_otp_via_sms(phone, new_otp_doc.otp)
        else:
            send_otp_via_sms(phone, new_otp_doc.otp)
    send_otp_via_email(new_otp_doc.otp, email)
    new_otp_doc.save(ignore_permissions=True)
    create_lead(email, phone, fname, lname, company_name, site_name)
    frappe.db.commit()
    return unique_id

@frappe.whitelist(allow_guest=True)
def verify_account_request(unique_id, otp):
    doc = frappe.db.get_all(
        "OTP", filters={"id": unique_id}, fields=["otp", "modified"]
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
    user = frappe.new_doc("SaaS Users")
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.linked_to_site = site
    user.phone = phone
    user.save(ignore_permissions=True)
    frappe.db.commit()
    return user

@frappe.whitelist(allow_guest=True)
def get_sites(email):
    return frappe.get_all(
        "SaaS Sites",
        filters={"linked_email": email},
        fields=["name", "site_name"],
    )

@frappe.whitelist(allow_guest=True)
def check_user_name_and_password_for_a_site(site_name, email, password):
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
    # stripe_subscription_manager = StripeSubscriptionManager(country=country)
    # has_sub = stripe_subscription_manager.has_valid_site_subscription(site.cus_id)
    has_sub = True
    # find user and check if has role of Administator
    hasRoleAdmin = frappe.db.exists(
        "Has Role", {"parent": email, "role": "Administrator"}
    )
    if not has_sub:
        return "NO_SUBSCRIPTION"
    return "OK"

@frappe.whitelist()
def create_lead(email, phone, fname, lname, company_name, site_name):	
    existing_lead = frappe.get_value("Lead",filters={"email_id": email})
    if existing_lead:
        lead_doc = frappe.get_doc("Lead",existing_lead,ignore_permissions=True)
        lead_doc.email_id = email
        lead_doc.mobile_no = phone
        lead_doc.first_name = fname
        lead_doc.last_name = lname
        lead_doc.lead_name = fname+" "+lname
        lead_doc.company_name = company_name
        lead_doc.save(ignore_permissions=True)
    else:
        lead = frappe.get_doc({
                "doctype":"Lead",
                "email_id": email,
                "mobile_no": phone,
                "status": "Lead",
            })
        lead.lead_owner = frappe.get_all("User",filters={
			"name": "Administrator"
		})[0].get("name")
        lead.first_name = fname
        lead.last_name = lname
        lead.lead_name = fname+" "+lname
        lead.company_name = company_name
        lead.save(ignore_permissions=True)
class SaaSUsers(Document):
    pass
