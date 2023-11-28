from . import __version__ as app_version

app_name = "bettersaas"
app_title = "Bettersaas"
app_publisher = "OneHash"
app_description = "This app manages multi tenancy"
app_email = "digital@onehash.ai"
app_license = "MIT"

# Includes in <head>
# ------------------ 

# include js, css files in header of desk.html
# app_include_css = "/assets/bettersaas/css/bettersaas.css"
# app_include_js = "/assets/bettersaas/js/bettersaas.js"

# include js, css files in header of web template
# web_include_css = "/assets/bettersaas/css/bettersaas.css"
# web_include_js = "/assets/bettersaas/js/bettersaas.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bettersaas/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bettersaas.utils.jinja_methods",
# 	"filters": "bettersaas.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bettersaas.install.before_install"
# after_install = "bettersaas.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "bettersaas.uninstall.before_uninstall"
# after_uninstall = "bettersaas.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bettersaas.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# Import necessary modules


scheduler_events = {
    "monthly": [
        "bettersaas.api.reset_email_limits",
    ],
    "weekly": [
        "bettersaas.bettersaas.doctype.saas_site_backups.saas_site_backups.generateOneHashBackups"
    ],
    "hourly": [
        "bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.check_stock_sites",
        "bettersaas.api.check_stock_sites",
    ],
    "daily_long": [
        "bettersaas.api.update_user_saas_sites"
        # "bettersaas.api.delarchived",
        # "bettersaas.bettersaas.doctype.saas_sites.saas_sites.update_user_to_main_app",
    ],
    # "cron": {
    # "1-59 * * * *":[
    # 			"bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.refreshStockSites"
    # 	]
    # }
    # 'all': [
    #     'bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.schedule_refresh_stock_sites'
    # ]
    # "cron":{
    #     "*/1 * * * *": [
    #     "bettersaas.api.delete_free_sites"
    #     ],
    #  }
}

# Testing
# -------

# before_tests = "bettersaas.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bettersaas.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bettersaas.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bettersaas.utils.before_request"]
# after_request = ["bettersaas.utils.after_request"]

# Job Events
# ----------
# before_job = ["bettersaas.utils.before_job"]
# after_job = ["bettersaas.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bettersaas.auth.validate"
# ]
app_include_js = [
    "https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"
]
