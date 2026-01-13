# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe


def sync_store_item_from_item(doc, method=None):
	"""Sync disabled field from Item to Store Item (2-way sync)"""
	# Skip if this update came from Store Item sync
	if getattr(frappe.flags, "in_store_item_sync", False):
		return

	store_item_name = getattr(doc, "custom_store_item", None)
	if not store_item_name:
		return

	if not frappe.db.exists("Store Item", store_item_name):
		return

	# Set flag to prevent infinite loop
	frappe.flags.in_item_sync = True
	try:
		# Only sync disabled field (2-way)
		frappe.db.set_value("Store Item", store_item_name, "disabled", doc.disabled or 0)
		frappe.db.commit()
	finally:
		frappe.flags.in_item_sync = False


def delete_store_item_on_item_trash(doc, method=None):
	"""Prevent Item deletion if linked to Store Item."""
	if getattr(frappe.flags, "in_store_item_delete", False):
		return

	store_item_name = getattr(doc, "custom_store_item", None)
	if not store_item_name:
		return

	if not frappe.db.exists("Store Item", store_item_name):
		return

	# Prevent deletion if Store Item exists
	frappe.throw(
		f"Cannot delete Item {doc.name} because it is linked to Store Item {store_item_name}. "
		f"Delete the Store Item first.",
		title="Item Linked to Store Item"
	)
