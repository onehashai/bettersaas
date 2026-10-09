import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
import traceback
import uuid
from datetime import timedelta
from urllib.parse import urlparse

import frappe
import requests
from filelock import FileLock
from frappe.utils import cint, get_bench_path, now_datetime
from frappe.utils.password import decrypt


PROTOCOL_VERSION = 1
MAX_ATTEMPTS = 8
RETRY_DELAYS_SECONDS = (60, 300, 900, 3600, 10800, 21600, 21600)
MANAGED_CONFIG_KEYS = {
	"customer_id",
	"invoice_due_date",
	"max_email",
	"max_storage",
	"min_license",
	"plan_name",
	"price_id",
	"product_id",
	"saas_site_disabled",
	"site_expiry_date",
	"skip_subscription_expiry",
	"stripe_subscription_event_created",
	"subscription_ends_on",
	"subscription_expiry_grace_days",
	"subscription_id",
	"subscription_quantity",
	"subscription_starts_on",
	"subscription_status",
}


class PermanentCommandError(Exception):
	pass


def get_site_config_path(site_name):
	sites_path = os.path.realpath(os.path.join(get_bench_path(), "sites"))
	site_path = os.path.realpath(os.path.join(sites_path, site_name))
	if os.path.commonpath([sites_path, site_path]) != sites_path:
		frappe.throw("Invalid SaaS site name")
	config_path = os.path.join(site_path, "site_config.json")
	if not os.path.isfile(config_path):
		frappe.throw(f"Site config not found for {site_name}")
	return config_path


def get_site_config(site_name):
	return frappe.get_site_config(site_path=site_name)


def is_enterprise_site(site_name):
	try:
		return cint(get_site_config(site_name).get("enterprise")) == 1
	except Exception:
		return False


def _serialise_value(value):
	if value is None or isinstance(value, (str, int, float, bool)):
		return value
	return str(value)


def write_dummy_config(site_name, updates, increment_revision=False):
	config_path = get_site_config_path(site_name)
	site_path = os.path.dirname(config_path)
	locks_path = os.path.join(site_path, "locks")
	os.makedirs(locks_path, exist_ok=True)

	with FileLock(os.path.join(locks_path, "enterprise_management.lock"), timeout=30):
		with open(config_path) as config_file:
			config = json.load(config_file)
		for key, value in updates.items():
			value = _serialise_value(value)
			if value is None:
				config.pop(key, None)
			else:
				config[key] = value
		if increment_revision:
			config["enterprise_management_revision"] = (
				cint(config.get("enterprise_management_revision")) + 1
			)

		fd, temporary_path = tempfile.mkstemp(prefix=".site_config.", dir=site_path)
		try:
			with os.fdopen(fd, "w") as temporary_file:
				json.dump(config, temporary_file, indent=1, sort_keys=True)
				temporary_file.flush()
				os.fsync(temporary_file.fileno())
			os.chmod(temporary_path, os.stat(config_path).st_mode)
			os.replace(temporary_path, config_path)
		finally:
			if os.path.exists(temporary_path):
				os.unlink(temporary_path)
	return config


def get_managed_state(config):
	# Include missing values as null so a stale client-side value is removed.
	return {key: _serialise_value(config.get(key)) for key in sorted(MANAGED_CONFIG_KEYS)}


def update_desired_state(site_name, updates, reason="configuration update"):
	if not is_enterprise_site(site_name):
		return None
	unknown_keys = set(updates) - MANAGED_CONFIG_KEYS
	if unknown_keys:
		frappe.throw(
			f"Unsupported enterprise configuration keys: {', '.join(sorted(unknown_keys))}"
		)
	config = write_dummy_config(site_name, updates, increment_revision=True)
	if not config.get("enterprise_management_secret") or not cint(
		config.get("enterprise_management_provisioned")
	):
		_update_site_delivery_status(site_name, "Unprovisioned", None)
		return None
	return queue_reconciliation(site_name, reason=reason, config=config)


def queue_reconciliation(site_name, reason="manual reconciliation", config=None):
	config = config or get_site_config(site_name)
	if not cint(config.get("enterprise")):
		frappe.throw(f"{site_name} is not configured as an enterprise site")
	if not config.get("enterprise_management_secret") or not cint(
		config.get("enterprise_management_provisioned")
	):
		frappe.throw(f"Enterprise management is not provisioned for {site_name}")

	revision = cint(config.get("enterprise_management_revision"))
	if revision <= 0:
		config = write_dummy_config(site_name, {}, increment_revision=True)
		revision = cint(config.get("enterprise_management_revision"))
	payload = {
		"protocol_version": PROTOCOL_VERSION,
		"command_id": str(uuid.uuid4()),
		"site": site_name,
		"revision": revision,
		"state": get_managed_state(config),
	}

	frappe.db.set_value(
		"SaaS Remote Command",
		{"site": site_name, "status": ("in", ["Queued", "Retrying"])},
		"status",
		"Superseded",
		update_modified=False,
	)
	command = frappe.get_doc(
		{
			"doctype": "SaaS Remote Command",
			"site": site_name,
			"command_id": payload["command_id"],
			"revision": revision,
			"reason": reason,
			"payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
			"status": "Queued",
			"attempts": 0,
		}
	).insert(ignore_permissions=True)
	_update_site_delivery_status(site_name, "Queued", None)
	frappe.enqueue(
		"bettersaas.remote_management.deliver_command",
		queue="short",
		command_name=command.name,
		enqueue_after_commit=True,
		job_id=f"enterprise-reconcile::{command.name}",
	)
	return command.name


def _management_url(site_name, config, method):
	base_url = config.get("enterprise_management_url") or f"https://{site_name}"
	parsed = urlparse(base_url)
	if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
		frappe.throw(f"Enterprise management URL for {site_name} must be an HTTPS origin")
	return f"https://{parsed.netloc}/api/method/{method}"


def _signed_headers(site_name, key_id, secret, path, body):
	timestamp = str(int(time.time()))
	nonce = str(uuid.uuid4())
	canonical = "\n".join(
		("POST", path, timestamp, nonce, hashlib.sha256(body).hexdigest())
	).encode()
	signature = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
	return {
		"Content-Type": "application/json",
		"X-Bettersaas-Key-Id": key_id,
		"X-Bettersaas-Nonce": nonce,
		"X-Bettersaas-Site": site_name,
		"X-Bettersaas-Signature": f"sha256={signature}",
		"X-Bettersaas-Timestamp": timestamp,
	}


def _post_signed(site_name, method, payload, config=None):
	config = config or get_site_config(site_name)
	key_id = config.get("enterprise_management_key_id")
	secret = config.get("enterprise_management_secret")
	if not key_id or not secret:
		frappe.throw(f"Enterprise management is not provisioned for {site_name}")
	url = _management_url(site_name, config, method)
	path = urlparse(url).path
	body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
	return requests.post(
		url,
		data=body,
		headers=_signed_headers(site_name, key_id, secret, path, body),
		timeout=(5, 20),
		allow_redirects=False,
	)


def _response_message(response):
	data = response.json()
	return data.get("message", data)


def _update_site_delivery_status(site_name, status, error=None):
	if not frappe.db.exists("SaaS Sites", site_name):
		return
	frappe.db.set_value(
		"SaaS Sites",
		site_name,
		{
			"management_sync_status": status,
			"last_management_sync": now_datetime(),
			"last_management_error": (error or "")[:1000],
		},
		update_modified=False,
	)


def deliver_command(command_name):
	command = frappe.get_doc("SaaS Remote Command", command_name)
	if command.status in {"Succeeded", "Superseded"}:
		return
	command.status = "Running"
	command.attempts = cint(command.attempts) + 1
	command.last_attempt = now_datetime()
	command.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		payload = json.loads(command.payload)
		response = _post_signed(
			command.site,
			"clientside.enterprise_management.reconcile",
			payload,
		)
		if response.status_code in {401, 403}:
			raise PermanentCommandError(
				f"Client rejected management authentication ({response.status_code})"
			)
		if 400 <= response.status_code < 500 and response.status_code not in {408, 429}:
			raise PermanentCommandError(
				f"Client rejected management command ({response.status_code})"
			)
		response.raise_for_status()
		message = _response_message(response)
		if cint(message.get("revision")) < cint(command.revision):
			raise RuntimeError("Client acknowledged an older configuration revision")
		command.status = "Succeeded"
		command.completed_at = now_datetime()
		command.last_error = None
		command.next_attempt = None
		command.response_status = response.status_code
		_update_site_delivery_status(command.site, "Succeeded", None)
	except PermanentCommandError as error:
		command.status = "Failed"
		command.last_error = str(error)[:2000]
		command.next_attempt = None
		_update_site_delivery_status(command.site, "Failed", command.last_error)
	except Exception as error:
		command.last_error = f"{type(error).__name__}: {error}"[:2000]
		if cint(command.attempts) >= MAX_ATTEMPTS:
			command.status = "Failed"
			command.next_attempt = None
			_update_site_delivery_status(command.site, "Failed", command.last_error)
		else:
			delay_index = min(cint(command.attempts) - 1, len(RETRY_DELAYS_SECONDS) - 1)
			command.status = "Retrying"
			command.next_attempt = now_datetime() + timedelta(
				seconds=RETRY_DELAYS_SECONDS[delay_index]
			)
			_update_site_delivery_status(command.site, "Retrying", command.last_error)
		frappe.log_error(
			title=f"Enterprise reconciliation failed: {command.site}",
			message=traceback.format_exc(),
		)
	command.save(ignore_permissions=True)
	frappe.db.commit()


def process_due_commands():
	queued = frappe.get_all(
		"SaaS Remote Command",
		filters={"status": "Queued"},
		pluck="name",
		limit=100,
	)
	retrying = frappe.get_all(
		"SaaS Remote Command",
		filters={"status": "Retrying", "next_attempt": ("<=", now_datetime())},
		pluck="name",
		limit=100,
	)
	stale_running = frappe.get_all(
		"SaaS Remote Command",
		filters={
			"status": "Running",
			"last_attempt": ("<=", now_datetime() - timedelta(minutes=10)),
		},
		pluck="name",
		limit=100,
	)
	names = list(dict.fromkeys([*queued, *retrying, *stale_running]))
	for name in names:
		frappe.enqueue(
			"bettersaas.remote_management.deliver_command",
			queue="short",
			command_name=name,
			job_id=f"enterprise-reconcile::{name}",
			deduplicate=True,
		)
	return names


@frappe.whitelist()
def retry_command(command_name):
	frappe.only_for("System Manager")
	command = frappe.get_doc("SaaS Remote Command", command_name)
	if command.status == "Succeeded":
		return {"status": "already_succeeded"}
	command.status = "Queued"
	command.next_attempt = None
	command.save(ignore_permissions=True)
	frappe.enqueue(
		"bettersaas.remote_management.deliver_command",
		queue="short",
		command_name=command.name,
		enqueue_after_commit=True,
		job_id=f"enterprise-reconcile::{command.name}",
	)
	return {"status": "queued"}


@frappe.whitelist()
def provision_enterprise_site(site_name):
	frappe.only_for("System Manager")
	config = get_site_config(site_name)
	if not cint(config.get("enterprise")):
		frappe.throw("Mark the dummy site config with enterprise = 1 before provisioning")

	key_id = config.get("enterprise_management_key_id") or f"emk_{uuid.uuid4().hex}"
	secret = config.get("enterprise_management_secret") or secrets.token_urlsafe(32)
	config = write_dummy_config(
		site_name,
		{
			"enterprise_management_key_id": key_id,
			"enterprise_management_secret": secret,
			"enterprise_management_provisioned": 0,
		},
	)

	site = frappe.get_doc("SaaS Sites", site_name)
	password = decrypt(site.encrypted_password, frappe.conf.encryption_key)
	base_url = _management_url(site_name, config, "").split("/api/method/")[0]
	session = requests.Session()
	login_response = session.post(
		f"{base_url}/api/method/login",
		data={"usr": "Administrator", "pwd": password},
		timeout=(5, 20),
		allow_redirects=False,
	)
	login_response.raise_for_status()
	bootstrap_response = session.post(
		f"{base_url}/api/method/clientside.enterprise_management.bootstrap",
		data={
			"key_id": key_id,
			"admin_url": frappe.utils.get_url(),
			"force": 1,
		},
		headers={"X-Bettersaas-Bootstrap-Secret": secret},
		timeout=(5, 20),
		allow_redirects=False,
	)
	bootstrap_response.raise_for_status()
	message = _response_message(bootstrap_response)
	if message.get("site") != site_name or message.get("key_id") != key_id:
		frappe.throw("Client returned an invalid provisioning acknowledgement")

	write_dummy_config(site_name, {"enterprise_management_provisioned": 1})
	return {"command": queue_reconciliation(site_name, "initial provisioning")}


@frappe.whitelist()
def reconcile_now(site_name):
	frappe.only_for("System Manager")
	config = write_dummy_config(site_name, {}, increment_revision=True)
	return {"command": queue_reconciliation(site_name, "manual reconciliation", config)}


@frappe.whitelist()
def rotate_enterprise_secret(site_name):
	frappe.only_for("System Manager")
	config = get_site_config(site_name)
	new_key_id = f"emk_{uuid.uuid4().hex}"
	new_secret = secrets.token_urlsafe(32)
	response = _post_signed(
		site_name,
		"clientside.enterprise_management.rotate_secret",
		{"new_key_id": new_key_id, "new_secret": new_secret},
		config,
	)
	response.raise_for_status()
	message = _response_message(response)
	if message.get("key_id") != new_key_id:
		frappe.throw("Client returned an invalid secret-rotation acknowledgement")
	write_dummy_config(
		site_name,
		{
			"enterprise_management_key_id": new_key_id,
			"enterprise_management_secret": new_secret,
		},
	)
	return {"key_id": new_key_id}
