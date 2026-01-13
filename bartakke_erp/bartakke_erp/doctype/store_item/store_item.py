# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StoreItem(Document):
	def after_insert(self):
		"""Create or link Item after Store Item is saved"""
		if not frappe.db.exists("Item", self.name):
			self.create_item()
		else:
			frappe.db.set_value("Item", self.name, "custom_store_item", self.name)
			frappe.db.commit()

	def on_update(self):
		"""Update linked Item when Store Item is updated"""
		item_name = frappe.db.get_value("Item", {"custom_store_item": self.name}, "name")
		if not item_name:
			return

		frappe.db.set_value("Item", item_name, {
			"item_code": self.name,
			"item_name": self.item_name or self.name,
			"item_group": self.item_group,
			"is_stock_item": self.is_stock_item or 1,
			"stock_uom": self.uom,
			"gst_hsn_code": self.hsn,
			"description": self.item_name or self.name,
			"custom_store_item": self.name,
			"custom_material_type": self.material_type,
			"custom_color": self.color,
			"custom_process": self.process_type,
			"standard_rate": self.price if self.price else None
		})
		frappe.db.commit()

	def on_trash(self):
		"""Delete linked Item when Store Item is deleted"""
		if getattr(frappe.flags, "in_store_item_delete", False):
			return

		item_name = frappe.db.get_value("Item", {"custom_store_item": self.name}, "name")
		if item_name:
			frappe.flags.in_store_item_delete = True
			try:
				frappe.delete_doc("Item", item_name, ignore_permissions=True, force=1)
			finally:
				frappe.flags.in_store_item_delete = False

	def create_item(self):
		"""Create Item from Store Item"""
		if frappe.db.exists("Item", self.name):
			return

		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": self.name,
			"item_name": self.item_name,
			"item_group": self.item_group,
			"stock_uom": self.uom,
			"is_stock_item": self.is_stock_item or 1,
			"custom_store_item": self.name,
			"gst_hsn_code": self.hsn,
			"description": self.item_name or self.name,
			"custom_material_type": self.material_type,
			"custom_color": self.color,
			"custom_process": self.process_type,
			"standard_rate": self.price if self.price else None
		})

		item.insert(ignore_permissions=True, set_name=self.name)
		frappe.db.commit()
		frappe.msgprint(f"Item {item.name} created successfully", alert=True, indicator="green")


@frappe.whitelist()
def create_item_from_store_item(store_item_name):
	"""Manually create Item from Store Item"""
	try:
		store_item = frappe.get_doc("Store Item", store_item_name)
		store_item.create_item()
		frappe.db.commit()
		return True
	except Exception as e:
		frappe.log_error(f"Error creating Item: {str(e)}", "Store Item to Item Creation Error")
		frappe.throw(f"Failed to create Item: {str(e)}")
