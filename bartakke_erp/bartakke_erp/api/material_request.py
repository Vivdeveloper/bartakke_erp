import frappe
from frappe import _
from frappe.utils import cstr, flt
import json

from erpnext.stock.get_item_details import get_item_details


def _planned_qty_by_mr_item(material_request):
	"""{material_request_item_name: total planned qty on open Production Plans}."""
	rows = frappe.db.sql(
		"""
		SELECT ppi.material_request_item AS name, SUM(ppi.planned_qty) AS qty
		FROM `tabProduction Plan Item` ppi
		INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
		WHERE ppi.material_request = %s AND pp.docstatus != 2
		GROUP BY ppi.material_request_item
		""",
		(material_request,),
		as_dict=True,
	)
	return {r.name: r.qty or 0 for r in rows}


def _resolve_bom_for_item(item_code, mr_bom=None, company=None):
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


def _mr_item_row_is_new(name):
	if not name:
		return True
	name = cstr(name).strip()
	if name.startswith("new-"):
		return True
	return not frappe.db.exists("Material Request Item", name)


def _assert_unique_item_codes_in_update_payload(items):
	seen = set()
	for upd in items:
		ic = (upd.get("item_code") or "").strip()
		if not ic:
			continue
		if ic in seen:
			frappe.throw(
				_("Each item can appear only once. Duplicate: {0}").format(ic),
				title=_("Update Items"),
			)
		seen.add(ic)


def _default_mr_item_warehouse(mr):
	if mr.get("set_warehouse"):
		return mr.set_warehouse
	for it in mr.get("items") or []:
		if it.get("warehouse"):
			return it.warehouse
	return None


def _append_mr_item_from_dialog(mr, item_code, qty, warehouse):
	if not warehouse:
		frappe.throw(_("Warehouse is required for new item {0}").format(item_code), title=_("Update Items"))
	if mr.material_request_type == "Manufacture":
		if not _resolve_bom_for_item(item_code, None, mr.company):
			frappe.throw(_("No active BOM for item {0}").format(item_code), title=_("Update Items"))

	args = frappe._dict(
		item_code=item_code,
		warehouse=warehouse,
		from_warehouse=None,
		doctype="Material Request",
		buying_price_list=mr.get("buying_price_list")
		or frappe.defaults.get_defaults().get("buying_price_list"),
		currency=frappe.db.get_value("Company", mr.company, "default_currency"),
		name=mr.name,
		qty=flt(qty),
		company=mr.company,
		conversion_rate=1,
		material_request_type=mr.material_request_type,
		plc_conversion_rate=1,
		transaction_date=mr.transaction_date,
		rate=0,
	)
	out = get_item_details(args, doc=mr, overwrite_warehouse=True) or {}
	schedule = mr.get("schedule_date") or mr.transaction_date
	row = mr.append(
		"items",
		{
			"item_code": item_code,
			"qty": flt(qty),
			"warehouse": warehouse,
			"schedule_date": schedule,
		},
	)
	for k, v in out.items():
		if k.startswith("_") or v is None:
			continue
		if row.meta.has_field(k):
			row.set(k, v)
	row.qty = flt(qty)
	row.warehouse = warehouse
	if schedule:
		row.schedule_date = schedule
	bom = _resolve_bom_for_item(item_code, None, mr.company)
	if bom:
		row.bom_no = bom


@frappe.whitelist()
def create_production_plan(material_request):
	mr = frappe.get_doc("Material Request", material_request)
	if mr.material_request_type != "Manufacture":
		frappe.throw(_("Material Request must be of type Manufacture"))

	pending = get_pending_items_for_production_plan(material_request, mr=mr)
	if not pending:
		frappe.throw(_("All items from this Material Request have already been fully planned in Production Plans"))

	pp = frappe.new_doc("Production Plan")
	pp.company = mr.company
	pp.get_items_from = "Material Request"
	pp.for_warehouse = "Unit-1 - BEPL"
	pp.custom_indent = mr.name
	pp.append("material_requests", {"material_request": mr.name, "material_request_date": mr.transaction_date})

	now = frappe.utils.now()
	for row in pending:
		item_code = row["item_code"]
		bom_no = _resolve_bom_for_item(item_code, row.get("bom_no"), mr.company)
		if not bom_no:
			frappe.throw(_("No active BOM for item {0}").format(item_code), title=_("Create Production Plan"))
		po_row = {
			"include_exploded_items": 1,
			"item_code": item_code,
			"bom_no": bom_no,
			"planned_qty": row["pending_qty"],
			"stock_uom": row["stock_uom"],
			"warehouse": row["warehouse"],
			"description": row["description"],
			"material_request": mr.name,
			"material_request_item": row["material_request_item"],
			"planned_start_date": now,
		}
		if row.get("custom_drawing_no"):
			po_row["custom_drawing_no"] = row["custom_drawing_no"]
		pp.append("po_items", po_row)

	pp.insert()
	frappe.msgprint(_("Production Plan {0} created successfully").format(pp.name))
	return pp.name


@frappe.whitelist()
def get_pending_items_for_production_plan(material_request, mr=None):
	mr = mr or frappe.get_doc("Material Request", material_request)
	planned = _planned_qty_by_mr_item(material_request)
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
				"resolved_bom": _resolve_bom_for_item(it.item_code, bom, mr.company),
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


@frappe.whitelist()
def update_material_request_qty(material_request, items):
	if isinstance(items, str):
		items = json.loads(items)

	_assert_unique_item_codes_in_update_payload(items)

	mr = frappe.get_doc("Material Request", material_request)
	if mr.material_request_type != "Manufacture":
		frappe.throw(_("Material Request must be of type Manufacture"))

	planned_qtys = {}
	for row in frappe.db.sql(
		"""
		SELECT ppi.material_request_item, SUM(ppi.planned_qty) AS total_planned_qty, ppi.item_code
		FROM `tabProduction Plan Item` ppi
		INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
		WHERE ppi.material_request = %s AND pp.docstatus != 2
		GROUP BY ppi.material_request_item
		""",
		(material_request,),
		as_dict=1,
	):
		planned_qtys[row.material_request_item] = {"qty": row.total_planned_qty or 0, "item_code": row.item_code}

	incoming_existing = set()
	for upd in items:
		nm = upd.get("name")
		if nm and not _mr_item_row_is_new(nm):
			incoming_existing.add(cstr(nm).strip())

	touched = False
	mr.flags.ignore_validate_update_after_submit = True

	for child in list(mr.items):
		if child.name in incoming_existing:
			continue
		ap = planned_qtys.get(child.name, {}).get("qty") or 0
		if ap > 0:
			frappe.throw(
				_("Cannot remove item {0}: {1} {2} already planned in Production Plans.").format(
					child.item_code, ap, child.stock_uom or _("Nos")
				),
				title=_("Update Items"),
			)
		mr.remove(child)
		touched = True

	for upd in items:
		name = upd.get("name")
		if _mr_item_row_is_new(name):
			item_code = (upd.get("item_code") or "").strip()
			qty = flt(upd.get("qty"))
			if not item_code:
				if qty <= 0:
					continue
				frappe.throw(_("Each new line needs an Item."), title=_("Update Items"))
			if qty <= 0:
				frappe.throw(_("Each new line needs a positive quantity."), title=_("Update Items"))
			wh = (upd.get("warehouse") or "").strip() or _default_mr_item_warehouse(mr)
			_append_mr_item_from_dialog(mr, item_code, qty, wh)
			touched = True
			continue

		name = cstr(name).strip()
		new_qty = upd.get("qty")
		if not name or new_qty is None:
			continue
		new_qty = flt(new_qty)
		if name in planned_qtys:
			ap, ic = planned_qtys[name]["qty"], planned_qtys[name]["item_code"]
			if new_qty < ap:
				frappe.throw(
					_("Cannot update quantity for item {0}. New quantity {1} is lower than already planned quantity {2} in Production Plans").format(
						ic, new_qty, ap
					)
				)
		child = next((r for r in mr.items if r.name == name), None)
		if not child:
			continue
		if child.parent != mr.name:
			frappe.throw(_("Invalid row reference."), title=_("Update Items"))
		if cstr(upd.get("item_code")).strip() != cstr(child.item_code).strip():
			frappe.throw(
				_("Item on row {0} cannot be changed here. Update quantity only, or add a new line.").format(child.idx),
				title=_("Update Items"),
			)
		if flt(child.qty) != new_qty:
			child.qty = new_qty
			touched = True

	if touched:
		if not mr.items:
			frappe.throw(_("Material Request must have at least one item."), title=_("Update Items"))
		mr.save()
		frappe.msgprint(_("Material Request updated successfully"))
	else:
		frappe.msgprint(_("No changes to save"))
	return True
