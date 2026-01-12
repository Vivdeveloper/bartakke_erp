# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe


def delete_store_item_on_item_trash(doc, method=None):
	"""Delete linked Store Item when Item is deleted."""
	if getattr(frappe.flags, "in_store_item_delete", False):
		return

	store_item_name = getattr(doc, "custom_store_item", None)
	if not store_item_name:
		return

	if not frappe.db.exists("Store Item", store_item_name):
		return

	frappe.flags.in_store_item_delete = True
	try:
		frappe.delete_doc("Store Item", store_item_name, ignore_permissions=True, force=1)
	finally:
		frappe.flags.in_store_item_delete = False
