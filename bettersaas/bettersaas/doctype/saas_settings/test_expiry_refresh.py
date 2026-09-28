import json
import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from bettersaas.bettersaas.doctype.saas_settings.saas_settings import (
    SaaSSettings,
    update_site_subscription_expiry_config,
)


class TestExpiryRefresh(TestCase):
    @patch(
        "bettersaas.bettersaas.doctype.saas_settings.saas_settings.frappe.log_error"
    )
    @patch(
        "bettersaas.bettersaas.doctype.saas_settings.saas_settings."
        "update_site_subscription_expiry_config"
    )
    @patch(
        "bettersaas.bettersaas.doctype.saas_settings.saas_settings.frappe.get_all"
    )
    def test_one_site_failure_does_not_block_later_sites(
        self,
        get_all,
        update_expiry_config,
        log_error,
    ):
        get_all.return_value = ["first.test", "second.test"]

        def fail_first_site(site_config_path, grace_days):
            if "first.test" in site_config_path:
                raise OSError("cannot update config")

        update_expiry_config.side_effect = fail_first_site

        with TemporaryDirectory() as bench_path:
            for site_name in get_all.return_value:
                site_path = os.path.join(bench_path, "sites", site_name)
                os.makedirs(site_path)
                with open(os.path.join(site_path, "site_config.json"), "w"):
                    pass

            with patch(
                "bettersaas.bettersaas.doctype.saas_settings.saas_settings."
                "frappe.utils.get_bench_path",
                return_value=bench_path,
            ), patch(
                "bettersaas.bettersaas.doctype.saas_sites.saas_sites."
                "get_subscription_expiry_grace_days",
                return_value=5,
            ):
                SaaSSettings.refresh_site_expiry_dates(object())

        updated_paths = [call.args[0] for call in update_expiry_config.call_args_list]
        self.assertTrue(any("second.test" in path for path in updated_paths))
        log_error.assert_called_once()

    def test_config_update_preserves_other_values(self):
        with TemporaryDirectory() as site_path:
            os.makedirs(os.path.join(site_path, "locks"))
            site_config_path = os.path.join(site_path, "site_config.json")
            with open(site_config_path, "w") as site_config_file:
                json.dump(
                    {
                        "subscription_status": "active",
                        "subscription_ends_on": "2026-10-01",
                    },
                    site_config_file,
                )

            update_site_subscription_expiry_config(
                site_config_path,
                grace_days=7,
            )

            with open(site_config_path) as site_config_file:
                site_config = json.load(site_config_file)

            self.assertTrue(
                os.path.isfile(os.path.join(site_path, "locks", "site_config.lock"))
            )
            self.assertTrue(
                os.path.isfile(
                    os.path.join(
                        site_path, "locks", "stripe_subscription_sync.lock"
                    )
                )
            )

        self.assertEqual(site_config["subscription_status"], "active")
        self.assertEqual(site_config["subscription_expiry_grace_days"], 7)
        self.assertEqual(site_config["site_expiry_date"], "2026-10-08")
