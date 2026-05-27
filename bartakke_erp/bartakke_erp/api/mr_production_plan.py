# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

"""Create Production Plan(s) from Material Request with optional qty split per item."""

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, now_datetime

from bartakke_erp.bartakke_erp.api.material_request import get_pending_items_for_production_plan
from bartakke_erp.bartakke_erp.api.mr_common import resolve_bom_for_item

DEFAULT_PP_WAREHOUSE = "Unit-1 - BEPL"


def _normalize_stock_uom(uom):
	"""Ensure stock_uom is a valid UOM name (avoids varchar length issues with bad values)."""
	uom = cstr(uom).strip()
	if uom and frappe.db.exists("UOM", uom):
		return uom
	default = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
	return default if frappe.db.exists("UOM", default) else "Nos"


def _parse_split_quantities(raw):
	if raw is None or raw == "":
		return []
	if isinstance(raw, list):
		return [flt(x) for x in raw if flt(x) > 0]
	text = cstr(raw).replace(";", ",")
	return [flt(p) for p in (x.strip() for x in text.split(",")) if p and flt(p) > 0]


def _get_mr_doc(material_request):
	mr = frappe.get_doc("Material Request", material_request)
	if mr.material_request_type != "Manufacture":
		frappe.throw(_("Material Request must be of type Manufacture"))
	return mr


def _pending_by_mr_item(material_request):
	return {row["material_request_item"]: row for row in get_pending_items_for_production_plan(material_request)}


@frappe.whitelist()
def get_mr_split_production_plan_rows(material_request):
	"""Rows for split dialog: pending qty, balance, BOM, drawing."""
	pending = get_pending_items_for_production_plan(material_request)
	rows = []
	for p in pending:
		item_code = p["item_code"]
		item_fields = frappe.db.get_value(
			"Item",
			item_code,
			["item_name", "custom_full_drawing_number_"],
			as_dict=True,
		) or {}
		rows.append(
			{
				"material_request_item": p["material_request_item"],
				"item_code": item_code,
				"item_name": item_fields.get("item_name") or item_code,
				"custom_full_drawing_number_": item_fields.get("custom_full_drawing_number_") or "",
				"requested_qty": flt(p["requested_qty"]),
				"already_planned": flt(p["already_planned"]),
				"pending_qty": flt(p["pending_qty"]),
				"balance_qty": flt(p["pending_qty"]),
				"stock_uom": _normalize_stock_uom(p.get("stock_uom")),
				"warehouse": p.get("warehouse"),
				"bom_no": p.get("resolved_bom") or p.get("bom_no"),
				"resolved_bom": p.get("resolved_bom"),
				"custom_drawing_no": p.get("custom_drawing_no"),
				"split_quantities": "",
			}
		)
	return rows


def _validate_split_rows(material_request, items):
	mr = _get_mr_doc(material_request)
	pending_map = _pending_by_mr_item(material_request)
	errors = []
	plan_groups = []

	for row in items:
		mri = cstr(row.get("material_request_item")).strip()
		if not mri:
			continue
		base = pending_map.get(mri)
		if not base:
			errors.append(_("Row {0}: no pending quantity on this Material Request.").format(row.get("item_code") or mri))
			continue

		splits = _parse_split_quantities(row.get("split_quantities"))
		if not splits:
			continue

		total = sum(splits)
		pending_qty = flt(base["pending_qty"])
		if total > pending_qty + 0.0001:
			errors.append(
				_("Item {0}: split total {1} exceeds pending balance {2}.").format(
					base["item_code"], total, pending_qty
				)
			)
			continue

		item_code = base["item_code"]
		bom_no = resolve_bom_for_item(item_code, row.get("bom_no") or base.get("bom_no"), mr.company)
		if not bom_no:
			errors.append(_("No active BOM for item {0}").format(item_code))
			continue

		for idx, qty in enumerate(splits):
			while len(plan_groups) <= idx:
				plan_groups.append([])
			plan_groups[idx].append(
				{
					"material_request_item": mri,
					"item_code": item_code,
					"planned_qty": qty,
					"stock_uom": _normalize_stock_uom(row.get("stock_uom") or base.get("stock_uom")),
					"warehouse": row.get("warehouse") or base.get("warehouse"),
					"description": base.get("description"),
					"bom_no": bom_no,
					"custom_drawing_no": row.get("custom_drawing_no") or base.get("custom_drawing_no"),
				}
			)

	if errors:
		frappe.throw("<br>".join(errors), title=_("Create Production Plan"))

	if not plan_groups:
		frappe.throw(_("Enter split quantities (e.g. 2,1,1,1) for at least one item."), title=_("Create Production Plan"))

	return plan_groups


@frappe.whitelist()
def preview_split_production_plans(material_request, items):
	if isinstance(items, str):
		items = json.loads(items)
	_get_mr_doc(material_request)
	plan_groups = _validate_split_rows(material_request, items)
	return {"plan_count": len(plan_groups)}


def _new_production_plan_shell(mr):
	pp = frappe.new_doc("Production Plan")
	pp.company = mr.company
	pp.get_items_from = "Material Request"
	pp.for_warehouse = DEFAULT_PP_WAREHOUSE
	pp.custom_indent = mr.name
	pp.posting_date = getdate()
	pp.append(
		"material_requests",
		{"material_request": mr.name, "material_request_date": mr.transaction_date},
	)
	return pp


def _safe_drawing_link(value):
	drawing = cstr(value).strip()
	if drawing and frappe.db.exists("Drawing", drawing):
		return drawing
	return None


def _append_po_item(pp, mr, line):
	qty = flt(line["planned_qty"])
	row = {
		"include_exploded_items": 1,
		"item_code": line["item_code"],
		"bom_no": line["bom_no"],
		"planned_qty": qty,
		"pending_qty": qty,
		"stock_uom": _normalize_stock_uom(line.get("stock_uom")),
		"warehouse": line.get("warehouse"),
		"description": line.get("description")
		or frappe.db.get_value("Item", line["item_code"], "description"),
		"material_request": mr.name,
		"material_request_item": line["material_request_item"],
		"planned_start_date": now_datetime(),
	}
	drawing = _safe_drawing_link(line.get("custom_drawing_no"))
	if drawing:
		row["custom_drawing_no"] = drawing
		if frappe.get_meta("Production Plan Item").has_field("drawing_no"):
			row["drawing_no"] = drawing

	po_row = pp.append("po_items", row)
	if hasattr(po_row, "_set_defaults"):
		po_row._set_defaults()


def _prepare_production_plan_rows(pp):
	if not pp.get("po_items"):
		frappe.throw(_("Production Plan must have at least one item."), title=_("Create Production Plan"))

	for row in pp.po_items:
		row.planned_qty = flt(row.planned_qty)
		if not flt(row.pending_qty):
			row.pending_qty = row.planned_qty
		if not row.description and row.item_code:
			row.description = frappe.db.get_value("Item", row.item_code, "description")
		if hasattr(row, "_set_defaults"):
			row._set_defaults()

	if hasattr(pp, "set_missing_values"):
		pp.set_missing_values()


def _populate_sub_assembly_items(doc):
	"""Same as Production Plan → Get Sub Assembly Items (ERPNext whitelist method)."""
	if not doc.get("po_items"):
		return doc

	if not doc.sub_assembly_warehouse and doc.for_warehouse:
		doc.sub_assembly_warehouse = doc.for_warehouse

	doc.get_sub_assembly_items()
	doc.save()
	return doc


def _save_production_plan(pp):
	"""Insert, save po_items, then fetch sub-assembly rows from BOM explosion."""
	_prepare_production_plan_rows(pp)

	pp.insert()
	frappe.db.commit()

	doc = frappe.get_doc(pp.doctype, pp.name)
	if hasattr(doc, "set_missing_values"):
		doc.set_missing_values()
	doc.save()
	frappe.db.commit()

	doc = _populate_sub_assembly_items(doc)
	frappe.db.commit()
	return doc


@frappe.whitelist()
def create_split_production_plans(material_request, items):
	if isinstance(items, str):
		items = json.loads(items)

	mr = _get_mr_doc(material_request)
	plan_groups = _validate_split_rows(material_request, items)

	created = []
	for lines in plan_groups:
		pp = _new_production_plan_shell(mr)
		for line in lines:
			_append_po_item(pp, mr, line)
		pp = _save_production_plan(pp)
		created.append(pp.name)

	return {"plans": created, "count": len(created)}
