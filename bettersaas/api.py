import frappe
from datetime import datetime,timedelta
from frappe.utils import add_to_date,getdate
import subprocess
from frappe.commands.site import drop_site

@frappe.whitelist()
def get_bench_details_for_cloudwatch():
    """
    API to get bench details for cloudwatch
    - number of created sites
    - number of active agents on our site
    - number of users who created site today
    - Number of stock sites
    """
    details = {}
    number_of_total_sites = frappe.db.count("SaaS sites")
    
    
@frappe.whitelist(allow_guest=True)
def delete_free_sites():
    config = frappe.get_doc("SaaS settings")
    sites = frappe.get_list('SaaS sites', fields=['site_name'])
    to_be_deleted = []
    for site in sites:
        try:
            config=frappe.get_site_config(site_path=site.site_name)
            if "plan" not in config or  (not config["plan"] )or len(config["plan"]) == 0:
                to_be_deleted.append(site)
        except:
            pass
    for site in to_be_deleted:
        # get last login of site from site config
        # if current date - last login date > 25 days and site has "has_subscription" as "no" then send warning mail
        # if current date - last login date >= 30 days and site has "has_subscription" as "no" then delete site
        config=frappe.get_site_config(site_path=site.site_name)
        # print all conditions
        if site.is_deleted != 'Yes' and ("has_subscription" in config) and config["has_subscription"] == "no" and "last_active" in config:
            
            last_login_date=config["last_active"]
            last_login_date = datetime.strptime(last_login_date, "%Y-%m-%d")
            present_date = frappe.utils.now_datetime().strftime("%Y-%m-%d")
            # present_date = datetime.date.today()
            present_date = datetime.strptime(present_date, "%Y-%m-%d")
            print("present date",present_date)
            print("last login date",last_login_date)
            inactive_days = (present_date - last_login_date).days
            print("inactive days",inactive_days)
            if inactive_days >=30 :
                print("deleting site")
                method = "bettersaas.api.drop_site_from_server"
                frappe.enqueue(method,queue="short",site_name=site.site_name)
            elif inactive_days >= 25:
                print("sending mail")
                email = site.linked_email
                content = 'This is to inform you that your OneHash account with the email address {e_address} will be permanently deleted on {exp_date}. You will no longer be able to access your account or recover any data'.format(e_address=email,exp_date = site.expiry_date.strftime("%d-%m-%y"))
                send_email(email, content)
    return "success"
def drop_site_from_server(site_name):
    config = frappe.get_doc("SaaS settings")
    doc = frappe.get_list("SaaS sites",filters={"site_name":site_name},fields=["site_name","name"])[0]
    frappe.utils.execute_in_shell("bench   drop-site {site} --root-password {db_root_password} --force --no-backup".format(site=doc["site_name"],db_root_password=config.db_password))
    docs = frappe.get_doc("SaaS sites",doc["name"])
    docs.is_deleted = "Yes"
    docs.save(ignore_permissions=True)
def send_email(email, content,):
    template = 'account_status_email'
    subject = 'Account Status'
    args = {
        "title": subject,
        "content": content
    }
    frappe.sendmail(
        recipients=email,
        template=template,
        subject=subject,
        args=args,
    )
    return 1
def testss():
    print("hello")
    frappe.msgprint("hello")