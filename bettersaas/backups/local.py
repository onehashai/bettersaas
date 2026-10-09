from __future__ import annotations

import gzip
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import frappe
from frappe.utils import cint, get_bench_path, now_datetime
from frappe.utils.background_jobs import enqueue

from bettersaas.remote_management import is_enterprise_site


DEFAULT_BACKUP_COUNT = 7
DEFAULT_MIN_FREE_GB = 20
DEFAULT_FILE_RETENTION_HOURS = 24
BACKUP_TIMEOUT_SECONDS = 2 * 60 * 60
SITE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
DATABASE_SUFFIXES = ("-database.sql.gz", "-database-enc.sql.gz")
CONFIG_SUFFIXES = ("-site_config_backup.json", "-site_config_backup-enc.json")
FILE_SUFFIXES = (
	"-files.tar",
	"-private-files.tar",
	"-files.tgz",
	"-private-files.tgz",
	"-files-enc.tar",
	"-private-files-enc.tar",
	"-files-enc.tgz",
	"-private-files-enc.tgz",
)
LEGACY_ZIP_RE = re.compile(r"^\d{8}_\d{6}-.+\.zip$")


def schedule_nightly_database_backups():
	"""Queue one database-only backup for the control site and every active tenant."""
	cleanup_all_site_backups()
	sites = {frappe.local.site}
	sites.update(
		frappe.get_all(
			"SaaS Sites",
			filters={"status": "Active"},
			pluck="site_name",
		)
	)

	queued = []
	for site in sorted(filter(None, sites)):
		if site != frappe.local.site and is_enterprise_site(site):
			continue
		if not _site_path(site).is_dir():
			frappe.log_error(f"Site directory does not exist: {site}", "Local backup skipped")
			continue

		enqueue(
			"bettersaas.backups.local.backup_site_database",
			queue="long",
			timeout=BACKUP_TIMEOUT_SECONDS,
			job_id=f"local-db-backup::{site}::{now_datetime().date().isoformat()}",
			deduplicate=True,
			site=site,
		)
		queued.append(site)

	return queued


def cleanup_all_site_backups():
	"""Bound stale local artifacts even for inactive, archived, and unused stock sites."""
	sites_root = Path(get_bench_path()) / "sites"
	for path in sites_root.iterdir():
		if not path.is_dir() or not (path / "site_config.json").is_file():
			continue
		if is_enterprise_site(path.name):
			continue
		try:
			cleanup_site_backups(path.name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Local backup cleanup failed: {path.name}")


def backup_site_database(site: str):
	"""Create and verify a native Frappe database backup, then apply local retention."""
	site_path = _site_path(site)
	if not site_path.is_dir():
		raise FileNotFoundError(f"Site directory does not exist: {site}")

	cleanup_site_backups(site)
	_assert_disk_reserve(site_path)

	before = set(_database_backups(site_path))
	keep = max(1, cint(frappe.conf.get("local_backup_count")) or DEFAULT_BACKUP_COUNT)
	_run_bench(
		["--site", site, "set-config", "keep_backups_for_hours", str((keep + 1) * 24)],
		site,
	)
	_run_bench(["--site", site, "backup"], site)

	created = sorted(set(_database_backups(site_path)) - before, key=lambda path: path.stat().st_mtime)
	if not created:
		raise RuntimeError(f"Backup command completed but created no database backup for {site}")
	for path in created:
		if path.stat().st_size == 0:
			raise RuntimeError(f"Backup command created an empty file: {path.name}")
		_verify_database_file(path)
		_verify_config_file(path)

	cleanup_site_backups(site)
	return {"site": site, "database_backup": created[-1].name}


def cleanup_site_backups(site: str):
	"""Bound native DB backups and expire legacy full-file artifacts owned by backup jobs."""
	site_path = _site_path(site)
	backup_path = site_path / "private" / "backups"
	backup_path.mkdir(parents=True, exist_ok=True)

	keep = max(1, cint(frappe.conf.get("local_backup_count")) or DEFAULT_BACKUP_COUNT)
	file_hours = max(
		1,
		cint(frappe.conf.get("local_file_backup_retention_hours"))
		or DEFAULT_FILE_RETENTION_HOURS,
	)
	cutoff = datetime.now() - timedelta(hours=file_hours)

	database_backups = sorted(_database_backups(site_path), key=lambda path: path.stat().st_mtime, reverse=True)
	for database_path in database_backups[keep:]:
		_delete_backup_set(database_path)

	for path in backup_path.iterdir():
		if path.is_file() and path.name.endswith(FILE_SUFFIXES):
			if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
				path.unlink(missing_ok=True)

	for path in (site_path / "private").iterdir():
		if path.is_file() and LEGACY_ZIP_RE.match(path.name):
			if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
				path.unlink(missing_ok=True)

	_remove_orphan_configs(backup_path, cutoff)


def disable_legacy_backup_jobs():
	"""Stop obsolete custom and off-site backup jobs after app migration."""
	patterns = (
		"%onehash_backups%",
		"%s3_backup_settings%",
		"%google_drive%backup%",
		"%dropbox_settings%backup%",
	)
	conditions = " OR ".join(["method LIKE %s"] * len(patterns))
	frappe.db.sql(
		f"UPDATE `tabScheduled Job Type` SET stopped = 1 WHERE {conditions}",  # nosec B608
		patterns,
	)


def _database_backups(site_path: Path) -> list[Path]:
	backup_path = site_path / "private" / "backups"
	if not backup_path.is_dir():
		return []
	return [
		path
		for path in backup_path.iterdir()
		if path.is_file() and path.name.endswith(DATABASE_SUFFIXES)
	]


def _delete_backup_set(database_path: Path):
	name = database_path.name
	prefix = next(name[: -len(suffix)] for suffix in DATABASE_SUFFIXES if name.endswith(suffix))
	database_path.unlink(missing_ok=True)
	for suffix in CONFIG_SUFFIXES + FILE_SUFFIXES:
		(database_path.parent / f"{prefix}{suffix}").unlink(missing_ok=True)


def _verify_database_file(path: Path):
	with path.open("rb") as stream:
		magic = stream.read(2)
	if magic != b"\x1f\x8b":
		# Encrypted dumps retain the .gz name but do not have a gzip header.
		return
	with gzip.open(path, "rb") as stream:
		while stream.read(1024 * 1024):
			pass


def _verify_config_file(database_path: Path):
	name = database_path.name
	prefix = next(name[: -len(suffix)] for suffix in DATABASE_SUFFIXES if name.endswith(suffix))
	config_paths = [database_path.parent / f"{prefix}{suffix}" for suffix in CONFIG_SUFFIXES]
	config_path = next((path for path in config_paths if path.is_file()), None)
	if not config_path:
		raise RuntimeError(f"Backup has no matching site configuration: {database_path.name}")
	with config_path.open(encoding="utf-8") as stream:
		if not isinstance(json.load(stream), dict):
			raise RuntimeError(f"Backup site configuration is invalid: {config_path.name}")


def _remove_orphan_configs(backup_path: Path, cutoff: datetime):
	database_prefixes = {
		next(path.name[: -len(suffix)] for suffix in DATABASE_SUFFIXES if path.name.endswith(suffix))
		for path in backup_path.iterdir()
		if path.is_file() and path.name.endswith(DATABASE_SUFFIXES)
	}
	for path in backup_path.iterdir():
		if not path.is_file() or not path.name.endswith(CONFIG_SUFFIXES):
			continue
		prefix = next(path.name[: -len(suffix)] for suffix in CONFIG_SUFFIXES if path.name.endswith(suffix))
		if prefix not in database_prefixes and datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
			path.unlink(missing_ok=True)


def _assert_disk_reserve(site_path: Path):
	minimum_gb = max(
		1,
		cint(frappe.conf.get("local_backup_min_free_gb")) or DEFAULT_MIN_FREE_GB,
	)
	free_bytes = shutil.disk_usage(get_bench_path()).free
	minimum_bytes = minimum_gb * 1024**3
	previous = _database_backups(site_path)
	estimated_bytes = max((path.stat().st_size * 2 for path in previous), default=1024**3)
	if free_bytes < minimum_bytes + estimated_bytes:
		raise RuntimeError(
			f"Local backup skipped: {free_bytes / 1024**3:.1f} GiB free; "
			f"{minimum_gb} GiB reserve plus {estimated_bytes / 1024**3:.1f} GiB "
			"estimated working space required"
		)


def _run_bench(arguments: list[str], site: str):
	result = subprocess.run(
		[_bench_command(), *arguments],
		cwd=get_bench_path(),
		capture_output=True,
		text=True,
		timeout=BACKUP_TIMEOUT_SECONDS,
		check=False,
	)
	if result.returncode:
		raise RuntimeError(
			f"Backup command failed for {site}: {(result.stderr or result.stdout)[-4000:]}"
		)
	return result


def _bench_command() -> str:
	configured = frappe.conf.get("local_backup_bench_command")
	if configured:
		return str(configured)
	command = shutil.which("bench")
	if not command:
		raise RuntimeError("bench executable was not found in PATH")
	return command


def _site_path(site: str) -> Path:
	if not site or not SITE_NAME_RE.fullmatch(site):
		raise ValueError(f"Invalid site name: {site!r}")
	root = (Path(get_bench_path()) / "sites").resolve()
	path = (root / site).resolve()
	if path.parent != root:
		raise ValueError(f"Invalid site path: {site!r}")
	return path
