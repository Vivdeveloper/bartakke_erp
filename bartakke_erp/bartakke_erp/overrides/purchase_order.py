import frappe
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder

class OverridePurchaseOrder(PurchaseOrder):
	def validate_fg_item_for_subcontracting(self):
		if self.is_subcontracted:
			if not self.is_old_subcontracting_flow:
				for item in self.items:
					if not item.fg_item:
						frappe.throw(
							_("Row #{0}: Finished Good Item is not specified for service item {1}").format(
								item.idx, item.item_code
							)
						)
					else:
						if not frappe.get_value("Item", item.fg_item, "is_sub_contracted_item"):
							frappe.throw(
								_("Row #{0}: Finished Good Item {1} must be a sub-contracted item").format(
									item.idx, item.fg_item
								)
							)
						elif not frappe.get_value("Item", item.fg_item, "default_bom"):
							pass
							# frappe.throw(
							# 	_("Row #{0}: Default BOM not found for FG Item {1}").format(
							# 		item.idx, item.fg_item
							# 	)
							# )
					if not item.fg_item_qty:
						frappe.throw(_("Row #{0}: Finished Good Item Qty can not be zero").format(item.idx))
		else:
			for item in self.items:
				item.set("fg_item", None)
				item.set("fg_item_qty", 0)