import frappe
from frappe import _


def validate_unique_gstin(doc, method=None):
	if not doc.get("gstin"):
		return

	doc.gstin = doc.gstin.strip().upper()

	duplicate = frappe.db.get_value(
		doc.doctype,
		{"gstin": doc.gstin, "name": ["!=", doc.name or ""]},
		"name",
	)
	if duplicate:
		frappe.throw(
			_("GSTIN {0} is already used by {1} {2}").format(
				frappe.bold(doc.gstin), doc.doctype, frappe.bold(duplicate)
			),
			title=_("Duplicate GSTIN"),
		)
