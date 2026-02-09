import frappe
from frappe import _
import json
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt


def validate_production_plan_qty(doc, method=None):
	"""
	Validate that Production Plan quantities don't exceed Material Request quantities
	"""
	if not doc.po_items:
		return

	# Group items by Material Request
	mr_items = {}
	for item in doc.po_items:
		if item.material_request and item.material_request_item:
			key = (item.material_request, item.material_request_item)
			if key not in mr_items:
				mr_items[key] = []
			mr_items[key].append(item)

	# Validate each Material Request item
	for (mr_name, mr_item_name), pp_items in mr_items.items():
		# Get the Material Request item
		mr_item = frappe.db.get_value(
			"Material Request Item",
			mr_item_name,
			["qty", "item_code", "stock_uom"],
			as_dict=1
		)

		if not mr_item:
			continue

		# Calculate total planned quantity from all Production Plans (excluding current and cancelled)
		total_planned = frappe.db.sql("""
			SELECT SUM(ppi.planned_qty) as total_planned
			FROM `tabProduction Plan Item` ppi
			INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
			WHERE ppi.material_request = %s
				AND ppi.material_request_item = %s
				AND pp.name != %s
				AND pp.docstatus != 2
		""", (mr_name, mr_item_name, doc.name), as_dict=1)

		already_planned = total_planned[0].total_planned if total_planned and total_planned[0].total_planned else 0

		# Calculate current document's planned quantity for this item
		current_planned = sum(item.planned_qty for item in pp_items)

		# Total planned quantity
		total = already_planned + current_planned

		# Check if exceeds Material Request quantity
		if total > mr_item.qty:
			frappe.throw(
				_("Row #{0}: Planned quantity {1} {2} for item {3} exceeds Indent Request {4} quantity of {5} {2}. Already planned: {6} {2}").format(
					pp_items[0].idx,
					current_planned,
					mr_item.stock_uom,
					mr_item.item_code,
					mr_name,
					mr_item.qty,
					already_planned
				)
			)

def set_missing_values(source, target):
    target.run_method("set_missing_values")
    target.run_method("calculate_taxes_and_totals")

    if hasattr(target, "set_use_serial_batch_fields"):
        target.run_method("set_use_serial_batch_fields")


@frappe.whitelist()
def make_so(source_name, target_doc=None, args=None):
    if not args:
        args = {}
    if isinstance(args, str):
        args = json.loads(args)

    def update_item(source, target, source_parent):
        qty = flt(source.pending_qty or source.planned_qty)

        target.qty = qty
        target.stock_qty = qty * flt(target.conversion_factor or 1)
        target.rate = frappe.db.get_value(
			"Item Price",
			{
				"item_code": target.item_code,
				"selling": 1
			},
			"price_list_rate"
		) or 0
        target.amount = qty * target.rate


    def select_item(d):
        filtered_items = args.get("filtered_children")
        return d.name in filtered_items if filtered_items else True

    doc = get_mapped_doc(
        "Production Plan",
        source_name,
        {
            "Production Plan": {
                "doctype": "Sales Order",
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Production Plan Item": {
                "doctype": "Sales Order Item",
                "field_map": {
                    "parent": "production_plan",
                },
                "condition": select_item,
                "postprocess": update_item,
            },
            "Sales Taxes and Charges": {
                "doctype": "Sales Taxes and Charges",
                "reset_value": True,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doc