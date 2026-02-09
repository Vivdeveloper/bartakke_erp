import frappe
from erpnext.controllers.subcontracting_controller import SubcontractingController
from frappe.utils import flt

class OverrideSubcontractingController(SubcontractingController):
	def validate_items(self):
		for item in self.items:
			is_stock_item, is_sub_contracted_item = frappe.get_value(
				"Item", item.item_code, ["is_stock_item", "is_sub_contracted_item"]
			)

			if not is_stock_item:
				frappe.throw(_("Row {0}: Item {1} must be a stock item.").format(item.idx, item.item_name))

			if not item.get("is_scrap_item"):
				if not is_sub_contracted_item:
					frappe.throw(
						_("Row {0}: Item {1} must be a subcontracted item.").format(item.idx, item.item_name)
					)

				if (
					self.doctype == "Subcontracting Order" and not item.subcontracting_conversion_factor
				):  # this condition will only be true if user has recently updated from develop branch
					service_item_qty = frappe.get_value(
						"Subcontracting Order Service Item",
						filters={"purchase_order_item": item.purchase_order_item, "parent": self.name},
						fieldname=["qty"],
					)
					item.subcontracting_conversion_factor = service_item_qty / item.qty

				if self.doctype not in "Subcontracting Receipt" and item.qty > flt(
					get_pending_subcontracted_quantity(self.purchase_order).get(item.purchase_order_item)
					/ item.subcontracting_conversion_factor,
					frappe.get_precision("Purchase Order Item", "qty"),
				):
					frappe.throw(
						_(
							"Row {0}: Item {1}'s quantity cannot be higher than the available quantity."
						).format(item.idx, item.item_name)
					)
				item.amount = item.qty * item.rate

				if item.bom:
					is_active, bom_item = frappe.get_value("BOM", item.bom, ["is_active", "item"])

					if not is_active:
						frappe.throw(
							_("Row {0}: Please select an active BOM for Item {1}.").format(
								item.idx, item.item_name
							)
						)
					if bom_item != item.item_code:
						frappe.throw(
							_("Row {0}: Please select an valid BOM for Item {1}.").format(
								item.idx, item.item_name
							)
						)
				else:
					item.rm_cost_per_qty = 0
					item.supplied_qty = 0
					item.consumed_qty = 0
			else:
				item.bom = None
				
def get_pending_subcontracted_quantity(po_name):
	table = frappe.qb.DocType("Purchase Order Item")
	query = (
		frappe.qb.from_(table)
		.select(table.name, table.qty, table.subcontracted_quantity)
		.where(table.parent == po_name)
	)
	return {item.name: item.qty - item.subcontracted_quantity for item in query.run(as_dict=True)}