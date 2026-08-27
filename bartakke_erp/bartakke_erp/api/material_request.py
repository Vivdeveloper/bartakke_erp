import frappe
from frappe.utils import flt

from bartakke_erp.bartakke_erp.api.mr_common import planned_qty_map, resolve_bom_for_item


@frappe.whitelist()
def get_pending_qty_for_purchase_order(material_request):
	mr = frappe.get_doc("Material Request", material_request)
	item_names = [it.name for it in mr.items]

	draft_qty_map = {}
	if item_names:
		draft_rows = frappe.get_all(
			"Purchase Order Item",
			filters={"material_request_item": ["in", item_names], "docstatus": 0},
			fields=["material_request_item", "stock_qty"],
		)
		for row in draft_rows:
			draft_qty_map[row.material_request_item] = draft_qty_map.get(
				row.material_request_item, 0
			) + flt(row.stock_qty)

	out = []
	for it in mr.items:
		if not it.item_code:
			continue
		submitted_ordered = flt(it.ordered_qty) or flt(it.received_qty) or 0
		draft_qty = draft_qty_map.get(it.name, 0)
		pending_qty = flt(it.stock_qty) - submitted_ordered - draft_qty
		out.append(
			{
				"name": it.name,
				"item_code": it.item_code,
				"item_name": it.item_name,
				"qty": it.qty,
				"uom": it.uom,
				"pending_qty": pending_qty,
				"draft_qty": draft_qty,
			}
		)
	return out


@frappe.whitelist()
def get_pending_items_for_production_plan(material_request, mr=None):
	mr = mr or frappe.get_doc("Material Request", material_request)
	planned = {k: v["qty"] for k, v in planned_qty_map(material_request).items()}
	out = []
	for it in mr.items:
		if not it.item_code:
			continue
		pending = flt(it.qty) - planned.get(it.name, 0)
		if pending <= 0:
			continue
		bom = it.bom_no or it.get("bom_no")
		out.append(
			{
				"item_code": it.item_code,
				"bom_no": bom,
				"resolved_bom": resolve_bom_for_item(it.item_code, bom, mr.company),
				"pending_qty": pending,
				"requested_qty": it.qty,
				"already_planned": planned.get(it.name, 0),
				"stock_uom": it.stock_uom,
				"warehouse": it.warehouse,
				"description": it.description,
				"material_request_item": it.name,
				"custom_drawing_no": it.get("custom_drawing_no"),
			}
		)
	return out
