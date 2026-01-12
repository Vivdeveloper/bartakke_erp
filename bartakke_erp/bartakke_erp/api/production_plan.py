import frappe
from frappe import _


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