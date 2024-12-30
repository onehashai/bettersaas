import frappe
import os
import sys
import requests
import click
import boto3
import datetime
from frappe.utils import cint
from frappe import _
from frappe.integrations.offsite_backup_utils import (
    generate_files_backup,
    get_latest_backup_file,
    validate_file_size,
)
from bettersaas.bettersaas.utils import (
    get_backup_size_of_site,
    get_database_size_of_site,
    get_total_files_size,
    convert_to_bytes,
    check_disk_size
)
from rq.timeouts import JobTimeoutException

@frappe.whitelist()
def get_context(context):
    def get_download_link(key):
        from botocore.client import Config
        from botocore.exceptions import ClientError

        bucket_name = frappe.conf.aws_bucket_name
        try:
            conn = boto3.client(
                "s3",
                aws_access_key_id=frappe.conf.aws_access_key_id,
                aws_secret_access_key=frappe.conf.aws_secret_access_key,
                config=Config(signature_version="s3v4", region_name="ap-south-1"),
            )
            url = conn.generate_presigned_url(
                "get_object", Params={"Bucket": bucket_name, "Key": key}, ExpiresIn=300
            )
            return url
        except ClientError as e:
            print(f"Error generating pre-signed URL: {e}")
            return None

    def get_time(created_on):
        created_on_datetime = datetime.datetime.strptime(created_on, "%Y-%m-%d %H:%M:%S.%f")
        return created_on_datetime.strftime("%a %b %d %H:%M %Y")

    req = requests.get(
        "http://"
        + frappe.conf.admin_url
        + "/api/method/bettersaas.bettersaas.doctype.saas_sites_backup.saas_sites_backup.get_backups?site="
        + frappe.local.site
    ).json()

    files = req["message"]
    filtered_files = [
        (
            get_download_link(file["path"]), 
            get_time(file["created_on"]),
            file["encrypted"],
            file["size"]
        )
        for file in files
    ]
    return {"files": filtered_files}

def encrypt_backup():
    return frappe.get_system_settings("encrypt_backup")

def backup_encryption(site_path):
    from shutil import which
    from frappe.utils.backups import get_or_generate_backup_encryption_key

    if which("gpg") is None:
        click.secho("Please install `gpg` and ensure its available in your PATH", fg="red")
        sys.exit(1)
    file_paths = [os.path.join(site_path, file) for file in os.listdir(site_path) if os.path.isfile(os.path.join(site_path, file))]
    for path in file_paths:
        if os.path.exists(path):
            if path.endswith(".json"):
                continue
            cmd_string = "gpg --yes --passphrase {passphrase} --pinentry-mode loopback -c {filelocation}"
        try:
            command = cmd_string.format(
                passphrase=get_or_generate_backup_encryption_key(),
                filelocation=path,
            )

            frappe.utils.execute_in_shell(command)
            os.rename(path + ".gpg", path)
        except Exception as err:
            print(err)
            click.secho(
                "Error occurred during encryption. Files are stored without encryption.", fg="red"
            )

def create_zip_with_files(zip_file_path, files_to_zip):
    import zipfile

    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files_to_zip:
            zipf.write(file_path, os.path.basename(file_path))

@frappe.whitelist()
def take_backups_s3(retry_count=0, backup_limit=3, site=None):
    try:
        validate_file_size()
        backup_to_s3(backup_limit=backup_limit, site=site)
    except JobTimeoutException:
        if retry_count < 2:
            take_backups_s3(
                retry_count=retry_count + 1,
                backup_limit=backup_limit,
                site=site,
            )
    except Exception:
        print(frappe.get_traceback())

def backup_to_s3(backup_limit, site):
    import boto3
    from frappe.utils import get_backups_path
    from frappe.utils.backups import new_backup

    bucket = frappe.conf.aws_bucket_name
    backup_files = True

    conn = boto3.client(
        "s3",
        aws_access_key_id=frappe.conf.aws_access_key_id,
        aws_secret_access_key=frappe.conf.aws_secret_access_key,
        region_name=frappe.conf.aws_bucket_region_name,
        endpoint_url="https://s3." + frappe.conf.aws_bucket_region_name + ".amazonaws.com",
    )
    bucket = frappe.conf.aws_bucket_name

    if frappe.flags.create_new_backup:
        backup = new_backup(
            ignore_files=False,
            backup_path_db=None,
            backup_path_files=None,
            backup_path_private_files=None,
            force=True,
        )
        db_filename = os.path.join(
            get_backups_path(), os.path.basename(backup.backup_path_db)
        )
        site_config = os.path.join(
            get_backups_path(), os.path.basename(backup.backup_path_conf)
        )
        if backup_files:
            files_filename = os.path.join(
                get_backups_path(), os.path.basename(backup.backup_path_files)
            )
            private_files = os.path.join(
                get_backups_path(), os.path.basename(backup.backup_path_private_files)
            )
    else:
        if backup_files:
            (
                db_filename,
                site_config,
                files_filename,
                private_files,
            ) = get_latest_backup_file(with_files=backup_files)

            if not files_filename or not private_files:
                generate_files_backup()
                (
                    db_filename,
                    site_config,
                    files_filename,
                    private_files,
                ) = get_latest_backup_file(with_files=backup_files)

        else:
            db_filename, site_config = get_latest_backup_file()

    folder = os.path.basename(db_filename)[:15] + "/"
    to_upload_config = []
    to_upload_config.append([db_filename, folder])
    to_upload_config.append([site_config, folder])

    if backup_files:
        if private_files:
            to_upload_config.append([private_files, folder])

        if files_filename:
            to_upload_config.append([files_filename, folder])

    server_keys = [x[0] for x in to_upload_config]
    replaced_site_name = site.replace(".", "_")
    target_zip_file_name = (
        to_upload_config[0][1][:-1] + "-" + replaced_site_name + ".zip"
    )
    on_server_zip_key = site + "/private/" + target_zip_file_name
    if encrypt_backup():
        backup_encryption(get_backups_path())
        
    create_zip_with_files(on_server_zip_key, server_keys)
    if frappe.conf.domain == "onehash.ai":
        dest_path = "production/site_backups/" + site + "/" + target_zip_file_name
    else:
        dest_path = "staging/site_backups/" + site + "/" + target_zip_file_name
    try:
        conn.upload_file(on_server_zip_key, bucket, dest_path)
        backup_size = check_disk_size("./" + site + "/private/" + target_zip_file_name) 
        try:
            insert_cmd = "bench --site {} execute bettersaas.bettersaas.doctype.saas_sites.saas_sites.insert_backup_record --args \"'{}','{}','{}','{}'\"".format(
                frappe.conf.admin_subdomain + "." + frappe.conf.domain, site, dest_path, backup_size, encrypt_backup()
                )
            frappe.utils.execute_in_shell(insert_cmd)
            delete_cmd = "bench --site {} execute bettersaas.bettersaas.doctype.saas_sites.saas_sites.delete_old_backups --args \"'{}','{}'\"".format(
                frappe.conf.admin_subdomain + "." + frappe.conf.domain, site, backup_limit
                )
            frappe.utils.execute_in_shell(delete_cmd)
            for key in server_keys:
                os.remove(key)
            os.remove(on_server_zip_key)
        except Exception as e:
            print(e)
    except Exception as e:
        print("Error uploading files to s3", e)

def get_scheduled_backup_limit():
	backup_limit = frappe.db.get_singles_value("System Settings", "backup_limit")
	return cint(backup_limit)

@frappe.whitelist()
def schedule_files_backup(site_name=None):
    from frappe.utils.background_jobs import enqueue, get_jobs

    frappe.only_for("System Manager")
    site_name = site_name or frappe.local.site
    queued_jobs = get_jobs(site=site_name, queue="long")
    method = "bettersaas.bettersaas.page.onehash_backups.onehash_backups.take_backups_s3"
    backup_limit = get_scheduled_backup_limit()

    if method not in queued_jobs[site_name]:
        enqueue(
            "bettersaas.bettersaas.page.onehash_backups.onehash_backups.take_backups_s3",
            queue="long",
            backup_limit=backup_limit,
            site=site_name
        )
        frappe.msgprint(_("Queued for backup."))
    else:
        frappe.msgprint(_("Backup job is already queued."))