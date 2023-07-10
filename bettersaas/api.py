import frappe
from datetime import datetime,timedelta
from frappe.utils import add_to_date,getdate
import subprocess


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
    sites = frappe.db.get_all('SaaS sites', fields=['*'], filters={
        'plan': "free"
    })
    present_date = getdate()
    for site in sites:
        if site.is_deleted != 'Yes':
            email = site.linked_email
            warning_mail_start_date = add_to_date(site.expiry_date)-timedelta(days=4)
            warning_mail_end_date = add_to_date(site.expiry_date)-timedelta(days=1)
            if warning_mail_start_date <= present_date <= warning_mail_end_date:
                content = 'This is to inform you that your OneHash account with the email address {e_address} will be permanently deleted on {exp_date}. You will no longer be able to access your account or recover any data'.format(e_address=email,exp_date = site.expiry_date.strftime("%d-%m-%y"))
                return send_email(email, content)

            elif present_date == add_to_date(site.expiry_date):
                subprocess.call('bench drop-site {s_name} --db-root-password {db_pass}'.format(s_name=site.site_name, db_pass='ris@123'), shell=True)
                content = 'We regret to inform you that your OneHash account with the email address {e_address} has be permanently deleted. Unfortunately, you will no longer be able to access your account or recover any data'.format(e_address=email)
                doc = frappe.get_doc('SaaS sites',site.name)
                doc.is_deleted = 'Yes'
                doc.save( ignore_permissions=True)
                return send_email(email, content)



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
