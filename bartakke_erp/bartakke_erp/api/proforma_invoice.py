import frappe
from frappe.model.mapper import get_mapped_doc


GST_RATE_FIELDS = ("cgst_rate", "sgst_rate", "igst_rate")


@frappe.whitelist()
def make_proforma_invoice(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.status = "Draft"

	def update_item(source, target, source_parent):
		# cgst_rate/sgst_rate/igst_rate are no_copy fields on Sales Order Item,
		# so the default mapper skips them and they need to be copied explicitly.
		for fieldname in GST_RATE_FIELDS:
			target.set(fieldname, source.get(fieldname))

	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Proforma Invoice",
				"field_map": {
					"name": "sales_order",
				},
			},
			"Sales Order Item": {
				"doctype": "Proforma Invoice Item",
				"postprocess": update_item,
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"add_if_empty": True,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doc
