from erpnext.subcontracting.doctype.subcontracting_order.subcontracting_order import SubcontractingOrder
import frappe
from frappe.utils import flt
from bartakke_erp.bartakke_erp.overrides.subcontracting_controller import OverrideSubcontractingController


class OverrideSubcontractingOrder(SubcontractingOrder,OverrideSubcontractingController):
	def calculate_supplied_items_qty_and_amount(self):
		for item in self.get("items"):
			if item.bom:
				bom = frappe.get_doc("BOM", item.bom)
				rm_cost = sum(flt(rm_item.amount) for rm_item in bom.items)
				item.rm_cost_per_qty = flt(rm_cost / flt(bom.quantity), item.precision("rm_cost_per_qty"))
			else:
				item.rm_cost_per_qty = 0