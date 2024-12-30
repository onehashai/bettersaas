# Copyright (c) 2024, OneHash and contributors
# For license information, please see license.txt

import frappe
import os
import boto3
from frappe.model.document import Document

@frappe.whitelist(allow_guest=True)
def get_backups(site):
    backups = frappe.db.get_list(
        "SaaS Sites Backup",
		filters={"site": site},
		fields=["*"],
        ignore_permissions=True
    )
    return backups
                    
def extract_zipfile(zip_file_path):
    import zipfile

    paths = [None, None, None, None]
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        extract_dir = os.path.splitext(zip_file_path)[0]
        zip_ref.extractall(extract_dir)

        for root, _, files in os.walk(extract_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if file_path.endswith('.gz'):
                    paths[0]=file_path
                elif 'private-files' in file_path and file_path.endswith('.tar'):
                    paths[1]=file_path
                elif file_path.endswith('.tar'):
                    paths[2]=file_path
                else:
                    paths[3]=file_path
    os.remove(zip_file_path)
    return [extract_dir, paths]

def download_backup(backup_id):
    from frappe.utils import get_backups_path

    conn = boto3.client(
        "s3",
        aws_access_key_id=frappe.conf.aws_access_key_id,
        aws_secret_access_key=frappe.conf.aws_secret_access_key,
    )
    bucket_name = frappe.conf.aws_bucket_name
    backup_doc = frappe.get_doc("SaaS Sites Backup", backup_id)
    download_path = os.path.join(get_backups_path(), os.path.basename(backup_doc.path))
    if not os.path.exists(download_path):
        conn.download_file(
            bucket_name,
            backup_doc.path,
            download_path,
        )
    return extract_zipfile(download_path)

def restore_site(*args, **kwargs):
    import shutil

    site_name = kwargs["site_name"]
    extract_dir, files_path = download_backup(kwargs["backup_id"])
    if int(kwargs.get("encrypted")):
        command = "bench --site {} --force restore {} --with-public-files {} --with-private-files {} --db-root-password {} --backup-encryption-key {}".format(
            site_name, files_path[0], files_path[2], files_path[1], frappe.conf.root_password, frappe.get_site_config(site_path=site_name).get("backup_encryption_key")
        )
    else:
        command = "bench --site {} --force restore {} --with-public-files {} --with-private-files {} --db-root-password {}".format(
            site_name, files_path[0], files_path[2], files_path[1], frappe.conf.root_password
        )
    frappe.enqueue(
        "bettersaas.bettersaas.doctype.saas_sites.saas_sites.execute_command_async",
        command=command,
        queue="short",
        now=True,
    )
    shutil.rmtree(extract_dir)
    frappe.publish_realtime(
        "site_restored", {"site_name": site_name}, user=frappe.session.user
    )
    return "Restored"
class SaaSSitesBackup(Document):
	pass
