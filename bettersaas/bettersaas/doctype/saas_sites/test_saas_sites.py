# Copyright (c) 2023, OneHash and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from clientside.stripe import StripeSubscriptionManager


class TestSaaSsites(FrappeTestCase):
    def setUp(self):
        self.args = {
            "company_name": "Test Company",
            "subdomain": frappe.utils.random_string(10),
            "password": frappe.utils.random_string(10),
            "first_name": "Test",
            "last_name": "User",
            "email": "tst@g.com",
            "phone": "1234567890",
            "country": "US",
            "allow_creating_users": "true",
        }
        self.args_us = {
            "company_name": "Test Company",
            "subdomain": frappe.utils.random_string(10),
            "password": frappe.utils.random_string(10),
            "first_name": "Test",
            "last_name": "User",
            "email": "tst@g.com",
            "phone": "1234567890",
            "country": "US",
            "allow_creating_users": "true",
        }
        from bettersaas.bettersaas.doctype.saas_sites.saas_sites import setupSite

        self.sub = setupSite(**self.args)["subdomain"]

    #   setupSite(**self.args_us)

    def test_create_site(self):
        site = frappe.get_all(
            "SaaS sites",
            filters={
                "site_name": self.args["subdomain"] + "." + frappe.conf.get("domain")
            },
        )
        self.assertEqual(len(site), 1)
        user = frappe.get_all(
            "SaaS users",
            filters={"site": self.args["subdomain"] + "." + frappe.conf.get("domain")},
        )
        self.assertEqual(len(user), 1)
        site_config = frappe.get_site_config(
            site_path=self.sub + "." + frappe.conf.get("domain")
        )
        self.assertTrue(site_config["customer_id"])
        print("counry", site_config["country"])
        stripe_subscription_manager = StripeSubscriptionManager(site_config["country"])
        has_sub = stripe_subscription_manager.get_subscriptions(
            site_config["customer_id"]
        )
        self.assertTrue(has_sub)
        has_sub = stripe_subscription_manager.get_onehash_subscription(
            site_config["customer_id"]
        )
        self.assertEqual(has_sub["status"], "trialing")

    # def test_create_site_us(self):
    #     # change country to US

    #     site = frappe.get_all(
    #         "SaaS sites",
    #         filters={
    #             "site_name": self.args_us["subdomain"] + "." + frappe.conf.get("domain")
    #         },
    #     )
    #     self.assertEqual(len(site), 1)
    #     user = frappe.get_all(
    #         "SaaS users",
    #         filters={
    #             "site": self.args_us["subdomain"] + "." + frappe.conf.get("domain")
    #         },
    #     )
    #     self.assertEqual(len(user), 1)
    #     site_config = frappe.get_site_config(
    #         site_path=self.sub + "." + frappe.conf.get("domain")
    #     )
    #     self.assertTrue(site_config["customer_id"])
    #     stripe_subscription_manager = StripeSubscriptionManager(site_config["country"])
    #     has_sub = stripe_subscription_manager.get_subscriptions(
    #         site_config["customer_id"]
    #     )
    #     self.assertTrue(has_sub)
    #     has_sub = stripe_subscription_manager.get_onehash_subscription(
    #         site_config["customer_id"]
    #     )
    #     self.assertEqual(has_sub["status"], "trialing")
    #     from bettersaas.api import drop_site_from_server

    #     drop_site_from_server(
    #         self.args_us["subdomain"] + "." + frappe.conf.get("domain")
    #     )

    def tearDown(self):
        from bettersaas.api import drop_site_from_server

        drop_site_from_server(self.args["subdomain"] + "." + frappe.conf.get("domain"))
        # drop_site_from_server(
        #     self.args_us["subdomain"] + "." + frappe.conf.get("domain")
        # )
