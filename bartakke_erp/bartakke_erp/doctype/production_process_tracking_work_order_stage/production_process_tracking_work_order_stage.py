# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class ProductionProcessTrackingWorkOrderStage(Document):
	def validate(self):
		if self.completed:
			if not self.completed_by:
				self.completed_by = frappe.session.user
			if not self.completed_on:
				self.completed_on = now()
			return

		self.completed_by = None
		self.completed_on = None
