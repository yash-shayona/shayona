from frappe.tests import IntegrationTestCase


class IntegrationTestOfferRecommendationItem(IntegrationTestCase):
    def test_child_doctype_is_available(self):
        import frappe

        meta = frappe.get_meta("Offer Recommendation Item")
        self.assertTrue(meta.istable)
        self.assertIsNotNone(meta.get_field("item_code"))
        self.assertIsNotNone(meta.get_field("minimum_qty"))
        self.assertIsNotNone(meta.get_field("discount_percentage"))
