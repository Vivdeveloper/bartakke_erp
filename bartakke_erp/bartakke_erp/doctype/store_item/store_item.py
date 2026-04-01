# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StoreItem(Document):
	def after_insert(self):
		"""Auto-create Item after Store Item is saved"""
		self.sync_item()

	def on_update(self):
		"""Auto-update Item when Store Item is updated"""
		self.sync_item()

	def validate(self):
		"""Validate before save"""
		# Check if another Store Item already links to this Item code
		if self.is_new():
			existing_link = frappe.db.get_value("Item", self.name, "custom_store_item")
			if existing_link and existing_link != self.name:
				frappe.throw(f"Item {self.name} is already linked to Store Item {existing_link}")

	# def on_trash(self):
	# 	"""Delete linked Item when Store Item is deleted"""
	# 	if getattr(frappe.flags, "in_store_item_delete", False):
	# 		return

	# 	item_name = frappe.db.get_value("Item", {"custom_store_item": self.name}, "name")
	# 	if item_name:
	# 		frappe.flags.in_store_item_delete = True
	# 		try:
	# 			frappe.delete_doc("Item", item_name, ignore_permissions=True, force=1)
	# 		finally:
	# 			frappe.flags.in_store_item_delete = False

	def sync_item(self):
		"""Create or update Item linked to Store Item"""
		# Skip if this update came from Item sync
		if getattr(frappe.flags, "in_item_sync", False):
			return

		# Find Item linked with Store Item
		existing_item = frappe.db.get_value("Item", {"custom_store_item": self.name}, "name")

		# Set flag to prevent infinite loop
		frappe.flags.in_store_item_sync = True
		try:
			if not existing_item:
				# CREATE ITEM (FIRST TIME)
				if not self.uom:
					frappe.throw("UOM is required to create Item")

				item = frappe.get_doc({
					"doctype": "Item",
					"item_code": self.name,
					"item_name": self.item_name,
					"item_group": self.item_group,
					"stock_uom": self.uom,
					"is_stock_item": self.is_stock_item or 1,
					"disabled": self.disabled or 0,
					"custom_store_item": self.name,
					"gst_hsn_code": self.hsn,
					"description": self.item_name or self.name,
					"custom_material_type": self.material_type,
					"custom_color": self.color,
					"custom_process": self.process_type,
					"standard_rate": self.price if self.price else None,
					"custom_development_size_a": self.custom_development_size_a if self.custom_development_size_a else 0,
					"custom_development_size_b": self.custom_development_size_b if self.custom_development_size_b else 0,
					"custom_area": self.custom_area if self.custom_area else 0,
					"custom_density": self.custom_density if self.custom_density else 0,
					"weight_per_unit": self.weight_per_unit if self.weight_per_unit else 0,
					"custom_t": self.custom_t if self.custom_t else 0
				})
				item.insert(ignore_permissions=True, set_name=self.name)
				frappe.msgprint(f"Item {item.name} created successfully", alert=True, indicator="green")
			else:
				# UPDATE + RENAME ITEM
				item = frappe.get_doc("Item", existing_item)

				# Rename Item code if Store Item name changed
				if item.name != self.name:
					frappe.rename_doc("Item", item.name, self.name, force=True, ignore_permissions=True)
					item = frappe.get_doc("Item", self.name)

				# Update remaining fields
				item.item_name = self.item_name
				item.item_group = self.item_group
				item.stock_uom = self.uom
				item.is_stock_item = self.is_stock_item or 1
				item.disabled = self.disabled or 0
				item.gst_hsn_code = self.hsn
				item.description = self.item_name or self.name
				item.custom_material_type = self.material_type
				item.custom_color = self.color
				item.custom_process = self.process_type
				item.standard_rate = self.price if self.price else None
				item.custom_development_size_a = self.custom_development_size_a if self.custom_development_size_a else 0
				item.custom_development_size_b = self.custom_development_size_b if self.custom_development_size_b else 0
				item.custom_area = self.custom_area if self.custom_area else 0
				item.custom_density = self.custom_density if self.custom_density else 0
				item.weight_per_unit = self.weight_per_unit if self.weight_per_unit else 0
				item.custom_t = self.custom_t if self.custom_t else 0

				item.save(ignore_permissions=True)

			frappe.db.commit()
		finally:
			frappe.flags.in_store_item_sync = False


@frappe.whitelist()
def create_item_from_store_item(store_item_name):
	"""Manually create/update Item from Store Item"""
	try:
		store_item = frappe.get_doc("Store Item", store_item_name)
		store_item.sync_item()
		return True
	except Exception as e:
		frappe.log_error(f"Error syncing Item: {str(e)}", "Store Item to Item Sync Error")
		frappe.throw(f"Failed to sync Item: {str(e)}")
