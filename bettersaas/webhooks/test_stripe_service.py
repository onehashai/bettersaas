from unittest import TestCase
from unittest.mock import patch

from bettersaas.webhooks import stripe_service


class TestStripeService(TestCase):
    def test_get_plan_name_from_live_subscription(self):
        stripe_prices = {
            "IN": {
                "products": {
                    "ONEHASH_CRM": {"product_id": "prod_crm"},
                    "ONEHASH_ERP": {"product_id": "prod_erp"},
                }
            }
        }
        subscription = {"plan": {"product": "prod_erp"}}

        with patch.object(
            stripe_service.frappe,
            "conf",
            {"stripe_prices": stripe_prices},
        ):
            plan_name = stripe_service.get_plan_name_from_subscription(
                subscription, "IN", fallback="OneHash_CRM"
            )

        self.assertEqual(plan_name, "OneHash_ERP")

    @patch("bettersaas.webhooks.stripe_service.update_subscription_config")
    @patch("bettersaas.webhooks.stripe_service.stripe.Subscription.retrieve")
    @patch("bettersaas.webhooks.stripe_service.frappe.get_site_config")
    @patch("bettersaas.webhooks.stripe_service.get_subscription_sync_lock")
    def test_sync_uses_plan_from_live_subscription(
        self,
        get_lock,
        get_site_config,
        retrieve_subscription,
        update_subscription_config,
    ):
        get_site_config.return_value = {"country": "US"}
        retrieve_subscription.return_value = {
            "plan": {"product": "prod_erp"},
        }
        stripe_prices = {
            "US": {
                "products": {
                    "ONEHASH_CRM": {"product_id": "prod_crm"},
                    "ONEHASH_ERP": {"product_id": "prod_erp"},
                }
            }
        }

        with patch.object(
            stripe_service.frappe,
            "conf",
            {"stripe_prices": stripe_prices},
        ):
            stripe_service.sync_subscription_by_id(
                "sub_123",
                "example.test",
                "OneHash_CRM",
                event_created=123,
            )

        update_subscription_config.assert_called_once_with(
            retrieve_subscription.return_value,
            "OneHash_ERP",
            "example.test",
            event_created=123,
        )
        get_lock.return_value.__enter__.assert_called_once_with()

