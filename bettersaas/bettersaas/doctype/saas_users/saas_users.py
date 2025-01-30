# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt

import frappe
import math
import random
import json
import requests
from frappe import _
from frappe.frappeclient import FrappeClient
from frappe.utils.password import decrypt
from frappe.model.document import Document


def get_stock_sites():
    req = requests.get(
            "http://"
            + frappe.conf.admin_url
            + "/api/method/bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.get_all_stock_sites"
        ).json()
    
    return req["message"]

@frappe.whitelist(allow_guest=True)
def check_user_name_and_password(site_name, email, password):
    try:
        conn = FrappeClient("http://"+site_name, email, password)
        if conn:
            return "VALID"
    except Exception as e:
        return "INVALID"

@frappe.whitelist(allow_guest=True)
def get_user_sites(email):
    if not email:
        return
    
    from frappe.utils import get_sites

    sites = get_sites()
    user_sites = []
    stock_sites = get_stock_sites()
    stock_subdomains_set = {site['subdomain'] for site in stock_sites}
    for site in sites:
        try:
            if site.split('.')[0] in stock_subdomains_set:
                continue

            if site == frappe.conf.admin_url:
                conn = FrappeClient("http://"+site, "Administrator", frappe.conf.administrator_password)
                user = conn.get_list('User', fields = ['name', 'email'], filters={'email': email}, limit_page_length=10000)
            else:
                saas_site = frappe.db.get("SaaS Sites", filters={"site_name": site})
                site_password = decrypt(saas_site.encrypted_password, frappe.conf.encryption_key)
                conn = FrappeClient("http://"+saas_site.name, "Administrator", site_password)
                user = conn.get_list('User', fields = ['name', 'email'], filters={'email': email}, limit_page_length=10000)

            if user:
                user_sites.append(site)

        except Exception:
            pass

    return {"user_sites": user_sites}

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


def send_otp_via_whatsapp(otp, phone):
    from frappe.integrations.utils import make_post_request

    api_version = frappe.conf.whatsapp_otp_config["api_version"]
    phone_number_id = frappe.conf.whatsapp_otp_config["phone_number_id"]
    access_token = frappe.conf.whatsapp_otp_config["access_token"]
    template_name = frappe.conf.whatsapp_otp_config["template_name"]
    language_code = frappe.conf.whatsapp_otp_config["language_code"]
    url = "https://graph.facebook.com"

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": [],
        },
    }
    param_1 = [{"type": "text", "text": otp}]
    param_2 = [{"type": "text", "text": otp}]
    data["template"]["components"].append(
        {
            "type": "body",
            "parameters": param_1,
        }
    )
    data["template"]["components"].append(
        {
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": param_2,
        }
    )

    headers = {
        "authorization": f"Bearer {access_token}",
        "content-type": "application/json",
    }

    try:
        make_post_request(
            f"{url}/{api_version}/{phone_number_id}/messages",
            headers=headers,
            data=json.dumps(data),
        )
    except Exception as e:
        res = frappe.flags.integration_request.json()["error"]
        error_message = res.get("Error", res.get("message"))
        frappe.throw(msg=error_message, title=res.get(
            "error_user_title", "Error"))


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
            frappe.utils.now(), doc[0].modified.strftime(
                "%Y-%m-%d %H:%M:%S.%f")
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

    try:
        send_otp_via_email(new_otp_doc.otp, email, fname)
    except Exception as e:
        frappe.log_error(message=str(e), title="Failed to send OTP via Email")

    try:
        send_otp_via_sms(new_otp_doc.otp, phone)
    except Exception as e:
        frappe.log_error(message=str(e), title="Failed to send OTP via SMS")

    try:
        send_otp_via_whatsapp(new_otp_doc.otp, phone)
    except Exception as e:
        frappe.log_error(message=str(
            e), title="Failed to send OTP via WhatsApp")

    new_otp_doc.save(ignore_permissions=True)
    create_lead(email, phone, fname, lname,
                company_name, site_name, url_params)
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
    existing_lead = frappe.get_value("Lead", filters={"email_id": email})
    if existing_lead:
        lead_doc = frappe.get_doc(
            "Lead", existing_lead, ignore_permissions=True)
        lead_doc.site_name = site_name
        lead_doc.site_status = "OTP Sended"
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
            "doctype": "Lead",
            "email_id": email,
            "mobile_no": phone,
            "status": "Lead",
        })
        lead.lead_owner = frappe.get_all("User", filters={
            "name": "Administrator"
        })[0].get("name")
        lead.site_name = site_name
        lead.site_status = "OTP Sended"
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
