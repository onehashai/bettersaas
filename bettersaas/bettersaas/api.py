import frappe
def upgrade_site(plan_metadata,subdomain):
    import subprocess as sp
    config = frappe.get_doc("SaaS settings")
    def set_config(key,value):
        try:
            sp.Popen("bench --site {} set-config {} {}".format(subdomain +"."+ config.domain,key,value),shell=True)
            frappe.utils.execute_in_shell("bench --site {} set-config {} {}".format(subdomain +"."+ config.domain,key,value))
        
        except Exception as e:
            print(e)
    plan = plan_metadata["product_id"]
    if plan in ["ONEHASH_PLUS","ONEHASH_STARTER","ONEHASH_PRO"]:
        set_config("plan",plan)
        if plan == "ONEHASH_PRO":
            set_config("max_users", "1000000")
        else:
            set_config("max_users", plan_metadata["user_count"])



            
        