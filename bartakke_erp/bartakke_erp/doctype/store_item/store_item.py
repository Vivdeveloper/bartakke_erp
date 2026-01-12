# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StoreItem(Document):
	def after_insert(self):
		"""Create Item after Store Item is inserted"""
		frappe.logger().info(f"after_insert triggered for Store Item: {self.name}")
		# Commit to ensure Store Item name is saved to database
		frappe.db.commit()
		self.create_item()

	def on_update(self):
		"""Sync linked Item fields when Store Item is updated"""
		self.update_linked_item()

	def on_trash(self):
		"""Delete linked Item when Store Item is deleted"""
		self.delete_linked_item()

	def update_linked_item(self):
		"""Update Item mapped from this Store Item"""
		item_name = frappe.db.get_value("Item", {"custom_store_item": self.name}, "name")
		if not item_name:
			return

		item = frappe.get_doc("Item", item_name)
		item.item_code = self.name
		item.item_name = self.item_name or self.name
		item.item_group = self.item_group
		item.is_stock_item = self.is_stock_item or 1
		item.stock_uom = self.uom
		item.gst_hsn_code = self.hsn
		item.description = self.item_name or self.name

		item.custom_store_item = self.name
		item.custom_material_type = self.material_type
		item.custom_color = self.color
		item.custom_process = self.process_type

		if self.price is not None:
			item.standard_rate = self.price

		item.save(ignore_permissions=True)
		frappe.db.commit()

	def delete_linked_item(self):
		"""Delete linked Item mapped from this Store Item"""
		if getattr(frappe.flags, "in_store_item_delete", False):
			return

		item_name = frappe.db.get_value("Item", {"custom_store_item": self.name}, "name")
		if not item_name:
			return

		frappe.flags.in_store_item_delete = True
		try:
			frappe.delete_doc("Item", item_name, ignore_permissions=True, force=1)
		finally:
			frappe.flags.in_store_item_delete = False

	def create_item(self):
		"""Create an Item from Store Item"""
		frappe.logger().info(f"create_item called for Store Item: {self.name}")

		# Check if Item already exists
		if frappe.db.exists("Item", {"custom_store_item": self.name}):
			frappe.logger().info(f"Item already exists for Store Item {self.name}, skipping")
			frappe.msgprint(f"Item already exists for Store Item {self.name}")
			return

		try:
			frappe.logger().info(f"Creating new Item with code: {self.name}, name: {self.item_name}")

			# Create new Item using get_doc to bypass naming series
			item = frappe.get_doc({
				"doctype": "Item",
				"item_code": self.name,  # Use Store Item .name as Item Code (e.g., "806017.302")
				"item_name": self.item_name or self.name,  # Use Store Item item_name field (e.g., "TTSUY")
				"item_group": self.item_group,
				"stock_uom": self.uom,
				"is_stock_item": self.is_stock_item or 1,
				"custom_store_item": self.name,  # Link back to Store Item .name
				"gst_hsn_code": self.hsn,
				"description": self.item_name or self.name
			})

			# Enforce item code as Store Item name before insert
			item.item_code = self.name

			# Set Material Type if custom field exists
			if self.material_type:
				item.custom_material_type = self.material_type

			# Set Color if custom field exists
			if self.color:
				item.custom_color = self.color

			# Set Process Type if custom field exists
			if self.process_type:
				item.custom_process = self.process_type

			# Set standard rate/price
			if self.price:
				item.standard_rate = self.price

			# Save the item - flags to prevent naming series override
			frappe.logger().info(f"Inserting Item with item_code={item.item_code}...")
			item.flags.ignore_mandatory = False
			item.insert(ignore_permissions=True, set_name=self.name)
			frappe.db.commit()

			frappe.logger().info(f"Item {item.name} created successfully")
			frappe.msgprint(f"Item {item.name} created successfully from Store Item {self.name}",
				alert=True, indicator="green")

		except Exception as e:
			error_msg = str(e)
			frappe.logger().error(f"Error creating Item from Store Item {self.name}: {error_msg}")
			frappe.log_error(f"Error creating Item: {error_msg}")
			frappe.msgprint(f"Failed to create Item: {error_msg}", alert=True, indicator="red")


@frappe.whitelist()
def create_item_from_store_item(store_item_name):
	"""Whitelisted method to manually create Item from Store Item"""
	store_item = frappe.get_doc("Store Item", store_item_name)
	store_item.create_item()
	return True
