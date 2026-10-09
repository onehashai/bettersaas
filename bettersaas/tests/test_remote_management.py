import hashlib
import hmac
from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from bettersaas import remote_management


class TestRemoteManagement(TestCase):
	def test_signed_headers_match_wire_body(self):
		body = b'{"revision":7}'
		path = "/api/method/clientside.enterprise_management.reconcile"
		with (
			patch.object(remote_management.time, "time", return_value=2_000_000_000),
			patch.object(remote_management.uuid, "uuid4", return_value="nonce-1"),
		):
			headers = remote_management._signed_headers(
				"enterprise.test", "emk_test_key", "a" * 32, path, body
			)

		canonical = "\n".join(
			(
				"POST",
				path,
				"2000000000",
				"nonce-1",
				hashlib.sha256(body).hexdigest(),
			)
		).encode()
		expected = hmac.new(b"a" * 32, canonical, hashlib.sha256).hexdigest()
		self.assertEqual(headers["X-Bettersaas-Signature"], f"sha256={expected}")

	def test_enterprise_url_rejects_plain_http(self):
		with self.assertRaises(Exception):
			remote_management._management_url(
				"enterprise.test",
				{"enterprise_management_url": "http://enterprise.test"},
				"clientside.enterprise_management.reconcile",
			)

	def test_desired_state_updates_dummy_before_queue(self):
		updated_config = {
			"enterprise": 1,
			"enterprise_management_secret": "a" * 32,
			"enterprise_management_provisioned": 1,
			"enterprise_management_revision": 4,
			"subscription_status": "active",
		}
		with (
			patch.object(remote_management, "is_enterprise_site", return_value=True),
			patch.object(
				remote_management,
				"write_dummy_config",
				return_value=updated_config,
			) as write_config,
			patch.object(
				remote_management, "queue_reconciliation", return_value="CMD-1"
			) as queue,
		):
			result = remote_management.update_desired_state(
				"enterprise.test",
				{"subscription_status": "active"},
				"test sync",
			)
		self.assertEqual(result, "CMD-1")
		write_config.assert_called_once_with(
			"enterprise.test", {"subscription_status": "active"}, increment_revision=True
		)
		queue.assert_called_once_with(
			"enterprise.test", reason="test sync", config=updated_config
		)

	def test_managed_state_never_contains_secret(self):
		state = remote_management.get_managed_state(
			{
				"enterprise_management_secret": "must-not-leak",
				"subscription_status": "active",
			}
		)
		self.assertNotIn("enterprise_management_secret", state)
		self.assertEqual(state["subscription_status"], "active")

	def test_transient_delivery_failure_is_scheduled_for_retry(self):
		command = SimpleNamespace(
			name="CMD-1",
			site="enterprise.test",
			status="Queued",
			attempts=0,
			revision=2,
			payload='{"revision":2}',
			last_attempt=None,
			last_error=None,
			next_attempt=None,
			completed_at=None,
			response_status=None,
			save=Mock(),
		)
		with (
			patch.object(remote_management, "now_datetime", return_value=datetime(2026, 10, 9)),
			patch.object(remote_management.frappe, "get_doc", return_value=command),
			patch.object(
				remote_management.frappe, "db", SimpleNamespace(commit=Mock())
			),
			patch.object(
				remote_management, "_post_signed", side_effect=requests.Timeout("offline")
			),
			patch.object(remote_management, "_update_site_delivery_status"),
			patch.object(remote_management.frappe, "log_error"),
		):
			remote_management.deliver_command(command.name)
		self.assertEqual(command.status, "Retrying")
		self.assertEqual(command.attempts, 1)
		self.assertIsNotNone(command.next_attempt)

	def test_authentication_failure_is_not_retried(self):
		command = SimpleNamespace(
			name="CMD-2",
			site="enterprise.test",
			status="Queued",
			attempts=0,
			revision=2,
			payload='{"revision":2}',
			last_attempt=None,
			last_error=None,
			next_attempt=None,
			completed_at=None,
			response_status=None,
			save=Mock(),
		)
		response = SimpleNamespace(status_code=401)
		with (
			patch.object(remote_management, "now_datetime", return_value=datetime(2026, 10, 9)),
			patch.object(remote_management.frappe, "get_doc", return_value=command),
			patch.object(
				remote_management.frappe, "db", SimpleNamespace(commit=Mock())
			),
			patch.object(remote_management, "_post_signed", return_value=response),
			patch.object(remote_management, "_update_site_delivery_status"),
		):
			remote_management.deliver_command(command.name)
		self.assertEqual(command.status, "Failed")
		self.assertIsNone(command.next_attempt)
