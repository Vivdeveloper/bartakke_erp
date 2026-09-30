import frappe


def execute():
	"""Blank strings break the unique index on Item.custom_full_drawing_number_ (NULLs don't)."""
	if not frappe.db.has_column("Item", "custom_full_drawing_number_"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabItem`
		SET custom_full_drawing_number_ = NULL
		WHERE TRIM(IFNULL(custom_full_drawing_number_, '')) = ''
		"""
	)
