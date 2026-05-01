# Copyright (c) 2026, Yash Solanki and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class TeaEntry(Document):
    def validate(self):
        self.total_amount = self.no_of_cups * self.rate_per_cup
