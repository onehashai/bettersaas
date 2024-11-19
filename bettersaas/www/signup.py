import frappe

def get_context(context):
 context.domain = frappe.conf.get('domain')
 return context