import frappe
import requests
import json

@frappe.whitelist(allow_guest=True)
def get_all_apps():
    url = "http://{site_name}/api/method/bettersaas.bettersaas.doctype.available_apps.available_apps.get_apps".format(
        site_name=frappe.conf.admin_url
    )
    try:
        site_apps = [x["app_name"] for x in frappe.utils.get_installed_apps_info()]
        res = json.loads(requests.get(url).text)
        apps_to_return = []
        for app in res["message"]:
            if app["app_name"] in site_apps:
                app["installed"] = "true"
            else:
                app["installed"] = "false"
            apps_to_return.append(app)
        return sorted(apps_to_return, key=lambda x: x["name"].lower())
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return e

@frappe.whitelist()
def install_app(*args, **kwargs):
    arr = []
    for key, value in kwargs.items():
        arr.append((key, value))
    app_name = arr[0][1]
    site_name = frappe.local.site
    frappe.utils.execute_in_shell(
        "bench --site {site_name} install-app {app_name}".format(
            site_name=site_name, app_name=app_name
        )
    )
    return "Success"

@frappe.whitelist()
def uninstall_app(*args, **kwargs):
    arr = []
    for key, value in kwargs.items():
        arr.append((key, value))
    app_name = arr[0][1]
    site_name = frappe.local.site
    frappe.utils.execute_in_shell(
        "bench --site {site_name} uninstall-app {app_name} --yes --no-backup".format(
            site_name=site_name, app_name=app_name
        )
    )
    return "Success"