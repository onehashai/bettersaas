# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt 

import frappe
import math
import random
import json
from frappe import _
from frappe.model.document import Document

def generate_otp():
    digits = "0123456789"
    OTP = ""
    for i in range(6):
        OTP += digits[math.floor(random.random() * 10)]
    return OTP

def send_otp_via_sms(otp, number):
    from frappe.core.doctype.sms_settings.sms_settings import send_sms
    receiver_list = []
    receiver_list.append(number)
    msg = otp + " is OTP to verify your account request for OneHash."
    send_sms(receiver_list, msg, sender_name="", success_msg=False)

def send_otp_via_email(otp, email, fname):
    subject = "Verify Email Address for OneHash"
    template = "signup_otp_email"
    args = {
        "first_name": fname,
        "otp": otp,
    }
    frappe.sendmail(
        recipients=email,
        subject=subject,
        template=template,
        args=args,
        delayed=False,
    )
    return True

@frappe.whitelist(allow_guest=True)
def send_otp(email, phone, fname, lname, company_name, site_name, url_params):
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
    new_otp_doc.email = email
    new_otp_doc.phone = phone
    send_otp_via_email(new_otp_doc.otp, email , fname)
    send_otp_via_sms(new_otp_doc.otp, phone)
    new_otp_doc.save(ignore_permissions=True)
    create_lead(email, phone, fname, lname, company_name, site_name, url_params)
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

@frappe.whitelist()
def create_lead(email, phone, fname, lname, company_name, site_name, url_params):	
    if url_params: 
        params = json.loads(url_params)
    existing_lead = frappe.get_value("Lead",filters={"email_id": email})
    if existing_lead:
        lead_doc = frappe.get_doc("Lead",existing_lead,ignore_permissions=True)
        lead_doc.site_name = site_name
        lead_doc.email_id = email
        lead_doc.mobile_no = phone
        lead_doc.first_name = fname
        lead_doc.last_name = lname
        lead_doc.lead_name = fname+" "+lname
        lead_doc.company_name = company_name
        if url_params:
            lead_doc.utm_source = params.get("utm_source", "")
            lead_doc.utm_medium = params.get("utm_medium", "")
            lead_doc.utm_campaign = params.get("utm_campaign", "")
            lead_doc.utm_content = params.get("utm_content", "")
            lead_doc.utm_term = params.get("utm_term", "")
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
        lead.site_name = site_name
        lead.first_name = fname
        lead.last_name = lname
        lead.lead_name = fname+" "+lname
        lead.company_name = company_name
        if url_params:
            lead.utm_source = params.get("utm_source", "")
            lead.utm_medium = params.get("utm_medium", "")
            lead.utm_campaign = params.get("utm_campaign", "")
            lead.utm_content = params.get("utm_content", "")
            lead.utm_term = params.get("utm_term", "")
        lead.save(ignore_permissions=True)
class SaaSUsers(Document):
    pass
