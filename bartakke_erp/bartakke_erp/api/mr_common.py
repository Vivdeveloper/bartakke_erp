"""Shared helpers for Material Request APIs (planned qty, BOM resolution)."""

import frappe
from frappe.utils import flt


def planned_qty_map(material_request):
	rows = frappe.db.sql(
		"""
		SELECT ppi.material_request_item AS name, ppi.item_code,
			SUM(ppi.planned_qty) AS qty
		FROM `tabProduction Plan Item` ppi
		INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
		WHERE ppi.material_request = %s AND pp.docstatus != 2
		GROUP BY ppi.material_request_item
		""",
		(material_request,),
		as_dict=True,
	)
	return {r.name: {"qty": flt(r.qty), "item_code": r.item_code} for r in rows}


def resolve_bom_for_item(item_code, mr_bom=None, company=None):
	"""MR BOM if valid for FG → Item default BOM → latest active BOM (company first)."""
	for nm in ((mr_bom or "").strip(), (frappe.db.get_value("Item", item_code, "default_bom") or "").strip()):
		if nm and frappe.db.get_value("BOM", nm, "item") == item_code:
			return nm
	filters = {"item": item_code, "docstatus": 1, "is_active": 1}
	for bom_filters in (({**filters, "company": company}, filters) if company else (filters,)):
		row = frappe.get_all(
			"BOM", filters=bom_filters, fields=["name"], order_by="is_default desc, modified desc", limit=1
		)
		if row:
			return row[0].name
	return None
