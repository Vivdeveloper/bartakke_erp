import frappe
from frappe.utils import flt

from bartakke_erp.bartakke_erp.api.mr_common import planned_qty_map, resolve_bom_for_item


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
