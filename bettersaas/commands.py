import click
import frappe
import sys
from frappe.commands import  pass_context
from frappe.exceptions import SiteNotSpecifiedError

@click.command("admin-site-backup")
@pass_context
def admin_site_backup(context):
    from bettersaas.bettersaas.page.onehash_backups.onehash_backups import schedule_files_backup
	
    exit_code = 0
    for site in context.sites:
        try:
            frappe.init(site=site)
            frappe.connect()
            schedule_files_backup(site)
        except Exception:
            click.secho(
                f"Backup failed for Site {site}. Database or site_config.json may be corrupted",
                fg="red",
            )
            exit_code = 1
            continue
        click.secho(
			"Backup for Site {} has been successfully completed".format(
				site
			),
			fg="green",
		)
        frappe.destroy()

    if not context.sites:
        raise SiteNotSpecifiedError

    sys.exit(exit_code)

commands = [
 admin_site_backup
]
