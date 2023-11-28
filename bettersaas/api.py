import frappe
from datetime import datetime, timedelta
from frappe.utils import add_to_date, getdate
import subprocess
from frappe.commands.site import drop_site
from frappe.utils import get_datetime, now, add_to_date
from frappe.utils import nowdate, nowtime
from frappe import _
from frappe.exceptions import DoesNotExistError
from frappe.utils import today, nowtime, add_days
from frappe.model.document import Document
from werkzeug.exceptions import ExpectationFailed
import os
import datetime
import shutil

@frappe.whitelist()
def get_days_since_creation(folder_path):
    try:
        creation_time = os.path.getctime(folder_path)
        creation_date = datetime.datetime.fromtimestamp(creation_time)
        days_since_creation = (datetime.datetime.now() - creation_date).days
        return days_since_creation
    except Exception as e:
        return f"An error occurred: {e}"

@frappe.whitelist()
def remove_folders_created_more_than_x_days(directory_path, threshold_days, folders_to_delete_limit):
    folders_to_delete_count = 0
    
    try:
        for folder_name in os.listdir(directory_path):
            if folders_to_delete_count >= folders_to_delete_limit:
                break
            
            folder_path = os.path.join(directory_path, folder_name)
            
            if os.path.isdir(folder_path):
                days_since_creation = get_days_since_creation(folder_path)
                
                if isinstance(days_since_creation, int) and days_since_creation > threshold_days:
                    shutil.rmtree(folder_path)
                    folders_to_delete_count += 1
    except Exception as e:
        frappe.msgprint(f"An error occurred: {e}")

@frappe.whitelist()
def delarchived():
    ss=frappe.get_doc('SaaS settings')

    directory_path = ss.path
    
    threshold_days = ss.threshold_days
    folders_to_delete_limit =ss.delete_limit
    frappe.msgprint(str(folders_to_delete_limit)+' Archived Sites Deleted Older than '+str(threshold_days)+' Days.')
    remove_folders_created_more_than_x_days(directory_path, threshold_days, folders_to_delete_limit)


@frappe.whitelist()
def update_user_saas_sites():
    admin_site_name = "app.onehash.is"
    frappe.destroy()
    frappe.init(site=admin_site_name)
    frappe.connect()
    try:
        all_sites = frappe.get_all("SaaS sites")
        for site in all_sites:
            current_site_name = site.name
            frappe.init(site=current_site_name)
            frappe.connect()
            enabled_system_users = frappe.get_all("User", fields=['name', 'email', 'last_active', 'user_type', 'enabled', 'first_name', 'last_name', 'creation'])

            site_doc = frappe.get_doc('SaaS sites', current_site_name)
            site_doc.user_details = []
            enabled_users_count = 0
            for user in enabled_system_users:
                if user.name in ['Administrator', 'Guest']:
                    continue

                site_doc.append('user_details', {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type,
                    'active': user.enabled,
                    'email_id': user.email,
                    'last_active': user.last_active
                })

                if user.enabled:
                    enabled_users_count += 1

            site_doc.number_of_users = len(enabled_system_users) - 2
            site_doc.number_of_active_users = enabled_users_count

            site_doc.save()

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(str(e))
    finally:
        frappe.destroy()


@frappe.whitelist()
def check_stock_sites():
    config = frappe.get_doc("SaaS settings")
    if not config.enabled:
        return
    if not config.run_at_interval:
        return
    curtime = nowtime()
    if curtime[:2] == "00":
        curtime = "24" + curtime[2:]

    if int(curtime[:2]) % int(config.run_at_interval) != 0:
        return

    delete_free_sites()


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


@frappe.whitelist()
def reset_email_limits():
    site_defaults = frappe.get_doc("SaaS settings")
    sites = frappe.get_all("SaaS sites", fields=["site_name"])
    total = frappe.db.count("SaaS sites")
    for i in range(0, total, 20):
        sites = frappe.get_all(
            "SaaS sites", fields=["site_name"], limit_start=i, limit_page_length=20
        )
        for site in sites:
            frappe.utils.execute_in_shell(
                "bench --site {} set-config max_email {}".format(
                    site["site_name"], site_defaults.default_email_limit
                )
            )


@frappe.whitelist(allow_guest=True)
def delete_free_sites():
    sites = frappe.get_list("SaaS sites", fields=["site_name"])
    to_be_deleted = []
    for site in sites:
        try:
            config = frappe.get_site_config(site_path=site.site_name)
            if "plan" not in config or (not config["plan"]) or len(config["plan"]) == 0:
                to_be_deleted.append(site)
        except:
            pass
    for site in to_be_deleted:
        # get last login of site from site config
        # if current date - last login date > 25 days and site has "has_subscription" as "no" then send warning mail
        # if current date - last login date >= 30 days and site has "has_subscription" as "no" then delete site
        config = frappe.get_site_config(site_path=site.site_name)
        # print all conditions
        if (
            site.is_deleted != "Yes"
            and ("has_subscription" in config)
            and config["has_subscription"] == "no"
            and "last_active" in config
        ):
            last_login_date = config["last_active"]
            last_login_date = datetime.strptime(last_login_date, "%Y-%m-%d")
            present_date = frappe.utils.now_datetime().strftime("%Y-%m-%d")
            # present_date = datetime.date.today()
            present_date = datetime.strptime(present_date, "%Y-%m-%d")
            print("present date", present_date)
            print("last login date", last_login_date)
            inactive_days = (present_date - last_login_date).days
            print("inactive days", inactive_days)
            if inactive_days >= config.inactive_for_days:
                print("deleting site")
                email = site.linked_email
                content = "This is to inform you that your OneHash account with the email address {e_address} has been permanently deleted on {exp_date}. You will no longer be able to access your account or recover any data".format(
                    e_address=email, exp_date=site.expiry_date.strftime("%d-%m-%y")
                )
                send_email(email, content)
                method = "bettersaas.api.drop_site_from_server"
                frappe.enqueue(method, queue="short", site_name=site.site_name)
            elif inactive_days >= config.inactive_for_days - config.warning_days:
                print("sending mail")
                email = site.linked_email
                content = "This is to inform you that your OneHash account with the email address {e_address} will be permanently deleted on {exp_date}. You will no longer be able to access your account or recover any data".format(
                    e_address=email, exp_date=site.expiry_date.strftime("%d-%m-%y")
                )
                send_email(email, content)
            elif (
                inactive_days
                >= config.inactive_for_days - config.intermittent_warning_day
            ):
                print("sending mail")
                email = site.linked_email
                content = "This is to inform you that your OneHash account with the email address {e_address} will be permanently deleted on {exp_date}. You will no longer be able to access your account or recover any data".format(
                    e_address=email, exp_date=site.expiry_date.strftime("%d-%m-%y")
                )
                send_email(email, content)
    return "success"


@frappe.whitelist()
def drop_site_from_server(site_name):
    print("deleting", site_name)
    doc = frappe.get_list(
        "SaaS sites", filters={"site_name": site_name}, fields=["site_name", "name"]
    )[0]
    decrypted_db_password = frappe.get_doc("SaaS settings").get_password("db_password")

    frappe.utils.execute_in_shell(
        "bench   drop-site {site} --root-password {db_root_password} --force --no-backup".format(
            site=doc["site_name"], db_root_password=decrypted_db_password
        )
    )


def send_email(
    email,
    content,
):
    config = frappe.get_doc("SaaS settings")
    template = config.deletion_warning_template
    subject = "Account Status"
    args = {"title": subject, "content": content}
    frappe.sendmail(
        recipients=email,
        template=template,
        subject=subject,
        args=args,
    )
    return 1


@frappe.whitelist()
def reset_sites():
    sites = frappe.get_all("SaaS sites", fields=["site_name"], limit_page_length=300)
    # delete record
    for site in sites:
        frappe.delete_doc("SaaS sites", sites["name"])
        print("deleting", site)
        command = "bench drop-site {} --force".format(site["site_name"])
        frappe.utils.execute_in_shell(command)
    frappe.db.commit()
    print("RESET")


def delete_all_sites():
    import os

    # find all sites in the "/home/frappe/frappe-bench/sites" directory
    # find all folders in current directory , make it dynamic
    files = os.listdir(os.getcwd())
    for file in files:
        # ignore .json files
        if file.endswith(".json"):
            continue
        print("site name", file)

        subdomain = file.split(".")[0]
        if subdomain == frappe.conf.get("admin_subdomain"):
            continue
        doc = frappe.get_list(
            "SaaS sites", filters={"site_name": file}, fields=["site_name", "name"]
        )
        if len(doc) == 1:
            frappe.delete_doc("SaaS sites", doc[0]["name"])
        # delete site
        config = frappe.get_doc("SaaS settings")
        config.db_password = config.get_password("db_password")
        frappe.utils.execute_in_shell(
            "bench drop-site {} --force --no-backup --db-root-password {}".format(
                file, config.db_password
            )
        )
