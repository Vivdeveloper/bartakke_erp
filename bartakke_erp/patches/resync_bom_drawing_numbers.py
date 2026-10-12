import frappe

from bartakke_erp.bartakke_erp.api.item import BOM_DRAWING_FIELDS


def execute():
	"""Re-sync BOM table drawing numbers that went stale after Item revision changes."""
	for doctype, item_field, drawing_field in BOM_DRAWING_FIELDS:
		if not frappe.db.has_column(doctype, drawing_field):
			continue

		frappe.db.sql(
			f"""
			UPDATE `tab{doctype}` t
			INNER JOIN `tabItem` i ON i.name = t.`{item_field}`
			SET t.`{drawing_field}` = i.custom_full_drawing_number_
			WHERE IFNULL(i.custom_full_drawing_number_, '') != ''
				AND IFNULL(t.`{drawing_field}`, '') != i.custom_full_drawing_number_
			"""
		)
