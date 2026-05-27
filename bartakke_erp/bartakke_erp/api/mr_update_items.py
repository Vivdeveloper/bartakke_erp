# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

"""Material Request → Update Items."""

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt

from erpnext.stock.get_item_details import get_item_details

from bartakke_erp.bartakke_erp.api.mr_common import planned_qty_map, resolve_bom_for_item

_TITLE = _("Update Items")
_DEFAULT_WH = "Stores - BEPL"


def _mr(material_request):
	mr = frappe.get_doc("Material Request", material_request)
	if mr.material_request_type != "Manufacture":
		frappe.throw(_("Material Request must be of type Manufacture"), title=_TITLE)
	return mr


def _bom(mr, item_code, bom_no=None):
	bom_no = (bom_no or "").strip()
	if bom_no and frappe.db.get_value("BOM", bom_no, "item") == item_code:
		return bom_no
	line = next((r for r in mr.items if r.item_code == item_code), None)
	return (line.bom_no if line else None) or resolve_bom_for_item(item_code, None, mr.company)


def _warehouse(mr):
	for wh in (mr.set_warehouse, *(r.warehouse for r in mr.items), _DEFAULT_WH):
		if wh and frappe.db.exists("Warehouse", wh):
			return wh
	return _DEFAULT_WH


def _is_new(name):
	name = cstr(name).strip()
	return not name or name.startswith("new-") or not frappe.db.exists("Material Request Item", name)


def _resolve_row_name(row, by_item):
	name = cstr(row.get("name") or "").strip()
	if name and not _is_new(name):
		return name
	ic = (row.get("item_code") or "").strip()
	matches = by_item.get(ic) or []
	return matches[0] if len(matches) == 1 else ""


def _validate_qty(item_code, qty, planned_qty=0):
	qty = flt(qty)
	if qty <= 0:
		frappe.throw(
			_(
				"Quantity must be greater than 0 for item {0}. "
				"Remove the row from the table to delete a line."
			).format(item_code),
			title=_TITLE,
		)
	if planned_qty > 0 and qty < flt(planned_qty):
		frappe.throw(
			_("Quantity for {0} cannot be less than planned quantity {1}.").format(item_code, planned_qty),
			title=_TITLE,
		)
	return qty


def _append_line(mr, item_code, qty, bom_no):
	wh, bom_no = _warehouse(mr), _bom(mr, item_code, bom_no)
	if not bom_no:
		frappe.throw(_("No active BOM for item {0}").format(item_code), title=_TITLE)

	row = mr.append(
		"items",
		{
			"item_code": item_code,
			"qty": flt(qty),
			"warehouse": wh,
			"schedule_date": mr.schedule_date or mr.transaction_date,
		},
	)
	details = get_item_details(
		frappe._dict(
			item_code=item_code,
			warehouse=wh,
			doctype="Material Request",
			name=mr.name,
			qty=flt(qty),
			company=mr.company,
			conversion_rate=1,
			material_request_type=mr.material_request_type,
			transaction_date=mr.transaction_date,
			rate=0,
		),
		doc=mr,
		overwrite_warehouse=True,
	) or {}
	for k, v in details.items():
		if not k.startswith("_") and v is not None and row.meta.has_field(k):
			row.set(k, v)
	row.qty, row.warehouse, row.bom_no = flt(qty), wh, bom_no


@frappe.whitelist()
def get_update_items_rows(material_request):
	mr = _mr(material_request)
	planned = planned_qty_map(material_request)
	return [
		{
			"name": r.name,
			"item_code": r.item_code,
			"item_name": r.item_name or r.item_code,
			"bom_no": _bom(mr, r.item_code, r.bom_no),
			"qty": r.qty,
			"planned_qty": flt(planned.get(r.name, {}).get("qty")),
			"stock_uom": r.stock_uom or "Nos",
		}
		for r in mr.items
		if r.item_code
	]


@frappe.whitelist()
def get_item_row_details(material_request, item_code):
	item_code = (item_code or "").strip()
	if not item_code:
		frappe.throw(_("Item is required"), title=_TITLE)
	item = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
	if not item:
		frappe.throw(_("Item {0} not found").format(item_code), title=_TITLE)

	mr = _mr(material_request)
	return {
		"item_code": item_code,
		"item_name": item.item_name or item_code,
		"stock_uom": item.stock_uom or "Nos",
		"bom_no": _bom(mr, item_code),
	}


@frappe.whitelist()
def update_items(material_request, items):
	if isinstance(items, str):
		items = json.loads(items)

	mr = _mr(material_request)
	by_item = {}
	for r in mr.items:
		by_item.setdefault(r.item_code, []).append(r.name)

	items = [{**dict(row), "name": _resolve_row_name(row, by_item) or row.get("name")} for row in items]

	seen = set()
	for row in items:
		ic = (row.get("item_code") or "").strip()
		if not ic:
			continue
		if ic in seen:
			frappe.throw(_("Each item can appear only once. Duplicate: {0}").format(ic), title=_TITLE)
		seen.add(ic)

	planned = planned_qty_map(material_request)
	keep = {_resolve_row_name(r, by_item) for r in items} - {""}
	touched = False
	mr.flags.ignore_validate_update_after_submit = True

	for child in list(mr.items):
		if child.name in keep:
			continue
		if planned.get(child.name, {}).get("qty"):
			frappe.throw(
				_("Cannot remove item {0}: {1} already planned in Production Plans.").format(
					child.item_code, planned[child.name]["qty"]
				),
				title=_TITLE,
			)
		mr.remove(child)
		touched = True

	for row in items:
		if _is_new(row.get("name")):
			ic = (row.get("item_code") or "").strip()
			if not ic:
				continue
			_append_line(mr, ic, _validate_qty(ic, row.get("qty")), row.get("bom_no"))
			touched = True
			continue

		child = next((r for r in mr.items if r.name == cstr(row["name"]).strip()), None)
		if not child:
			continue
		if cstr(row.get("item_code")).strip() != cstr(child.item_code).strip():
			frappe.throw(_("Item on row {0} cannot be changed.").format(child.idx), title=_TITLE)

		planned_qty = flt(planned.get(child.name, {}).get("qty"))
		new_qty = _validate_qty(child.item_code, row.get("qty"), planned_qty)
		if flt(child.qty) != new_qty:
			child.qty = new_qty
			touched = True

	if not touched:
		frappe.msgprint(_("No changes to save"))
		return True
	if not mr.items:
		frappe.throw(_("Material Request must have at least one item."), title=_TITLE)
	mr.save()
	frappe.msgprint(_("Material Request updated successfully"))
	return True
