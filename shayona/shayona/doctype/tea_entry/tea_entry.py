# Copyright (c) 2026, Yash Solanki and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TeaEntry(Document):
    def validate(self):
        self.set_total_amount()
        self.validate_duplicate_date()

    def set_total_amount(self):
        self.total_amount = (self.no_of_cups or 0) * (self.rate_per_cup or 0)

    def validate_duplicate_date(self):
        if not self.date:
            return
            
        existing_doc = frappe.db.exists(
            "Tea Entry",
            {
                "date": self.date,
                "name": ["!=", self.name],
            },
        )

        if existing_doc:
            frappe.throw(
                title="Duplicate Entry",
                msg=f"Tea Entry already exists for date <b>{self.date}</b>.",
            )
