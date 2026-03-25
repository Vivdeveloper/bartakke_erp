# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Drawing(Document):
    def autoname(self):
        if self.sheet:
            self.name = f"{self.sf_code}-{self.drawing_number}-{self.revision}/{self.sheet}"
        else:
            self.name = f"{self.sf_code}-{self.drawing_number}-{self.revision}"
	# pass
