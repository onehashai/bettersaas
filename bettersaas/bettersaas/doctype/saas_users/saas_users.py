# Copyright (c) 2023, OneHash and contributors
# For license information, please see license.txt 

import frappe
import math
import random
import requests
import json
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.utils.password import decrypt, encrypt
from clientside.stripe import StripeSubscriptionManager
import socket


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
    # ip_address = socket.gethostbyname(hostname)
    # docotp=frappe.get_all('OTP',filters={'ip':ip_address})
    # count=0
    # if docotp:
    #     for i in docotp:
    #         count+=1
    # if count<1:
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
        bcc=[""],
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
def send_otp(email, phone, fname, company_name, lname):
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
        new_otp_doc.ip = str(get_ip())

    else:
        print("GENERATING")
        new_otp_doc.otp = generate_otp()
        new_otp_doc.ip = str(get_ip())

    unique_id = frappe.generate_hash("", 5)

    new_otp_doc.id = unique_id
    
    new_otp_doc.ip = str(get_ip())

    new_otp_doc.email = email
    if phone:
        new_otp_doc.phone = phone
        from datetime import datetime

        docotp=frappe.get_list('OTP',fields=['*'],filters={'ip':str(get_ip()),'date':datetime.now().date()})
        if docotp:
            count=0
            for i in docotp:
                count+=1
            if count<=2:
                send_otp_sms(phone, new_otp_doc.otp)
        else:
            send_otp_sms(phone, new_otp_doc.otp)
    print(new_otp_doc.otp)

    #MrAbhi----------------------------------------------
    ws=frappe.get_doc('Wati Settings')
    token=ws.access_token
    api_endpoint=ws.api_endpoint
    # if len(str(phone))==10:
    #     mno='91'+str(phone)
    # else:
    mno=str(phone)
    url = f"{api_endpoint}/api/v2/sendTemplateMessage?whatsappNumber={mno}"

    payload = json.dumps({
    "template_name": "otp_signup",
    "broadcast_name": "Broadcast",
    "parameters": [
        {
        "name": "signup_otp",
        "value": new_otp_doc.otp
        },    
        {
        "name": "name",
        "value": fname+' '+lname
        },
        {
        "name": "doc",
        "value": "Lead"
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
    #MrAbhi : Create Lead ------------------------------------------------------------
    existing_lead = frappe.get_value("Lead",filters={"email_id":email})
    if(existing_lead):
        lead_doc = frappe.get_doc("Lead",existing_lead,ignore_permissions=True)

        lead_doc.email_id = email
        lead_doc.mobile_no = phone
        lead_doc.company_name = company_name
        lead_doc.first_name = fname
        lead_doc.last_name = lname
        lead_doc.product = "OneHash CRM"
        lead_doc.save(ignore_permissions=True)
        
    else:
        lead = frappe.get_doc({
        "doctype":"Lead",
        "email_id": email,
        "mobile_no": phone,
        "company_name": company_name,
        "status": "Lead",
        })
    
        lead.source = "Walk In"
        lead.save(ignore_permissions=True)
 #-------------------------------------------------------------------------------- 
    
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
    result = user.save(ignore_permissions=True)
    lead = create_lead(result)
    frappe.db.commit()
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
def get_users_list(site_name):
	site_password = get_decrypted_password("SaaS sites", site_name, "encrypted_password")
	domain = site_name
	from better_saas.better_saas.doctype.saas_user.frappeclient import FrappeClient
	conn = FrappeClient("https://"+domain, "Administrator", site_password)
	total_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name', 'enabled', 'last_active','user_type'],limit_page_length=10000)
	active_users = conn.get_list('User', fields = ['name', 'first_name', 'last_name','last_active','user_type'], filters = {'enabled':'1'},limit_page_length=10000)
	return {"total_users":total_users, "active_users":active_users}

@frappe.whitelist()
def get_all_users_of_a_site():
    site = "Samsun.localhost"
    a = frappe.db.sql(
        "select email from `tabSaaS users` where site = %s", site, as_dict=1
    )
    print(a)

#MrAbhi : Lead Creation ---------------------------------------------------------------------
@frappe.whitelist()
def create_lead(saas_user):	
    existing_lead = frappe.get_value("Lead",filters={"email_id":saas_user.email})
    if(existing_lead):
        lead_doc = frappe.get_doc("Lead",existing_lead,ignore_permissions=True)
        
        lead_doc.email_id = saas_user.email
        lead_doc.mobile_no = saas_user.phone
        lead_doc.lead_name = saas_user.first_name+" "+saas_user.last_name
        lead_doc.first_name = saas_user.first_name
        lead_doc.last_name = saas_user.last_name
        lead_doc.linked_saas_site = saas_user.site
        lead_doc.save(ignore_permissions=True)

        # saassite= frappe.get_doc("SaaS sites",saas_user.site,ignore_permissions=True)

        # saassite.append('user_details', {
        #             'first_name': saas_user.first_name,
        #             'last_name': saas_user.last_name,
        #             'user_type': 'System User',
        #             'active': 1,
        #             'email_id': saas_user.email,
        #             'last_active': ''
        #         })
        # saassite.number_of_users = 1
        # saassite.number_of_active_users= 1
        # saassite.save()
        
    else:
        lead = frappe.get_doc({
                "doctype":"Lead",
                "email_id": saas_user.email,
                "mobile_no": saas_user.phone,
                "status": "Lead",
                "linked_saas_site": saas_user.site
            })
        lead.lead_name = saas_user.first_name+" "+saas_user.last_name
        lead.source = "Walk In"
        lead.save(ignore_permissions=True)
#---------------------------------------------------------------------------------------------------
class SaaSusers(Document):
    pass


# 980555
