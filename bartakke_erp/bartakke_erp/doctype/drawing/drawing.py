# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Drawing(Document):
    def autoname(self):
        if self.sf_code and self.drawing_number:
            self.name = f"{self.sf_code}-{self.drawing_number}"
	# pass
