import frappe
from frappe import _
import json
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate, nowdate
from frappe.utils.data import cstr
import re


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
	
    def set_header_values(source, target, source_parent=None):
        target.customer = source.custom_customer_name

    doc = get_mapped_doc(
        "Production Plan",
        source_name,
        {
            "Production Plan": {
                "doctype": "Sales Order",
                "validation": {
                    "docstatus": ["=", 1],
                },
                "postprocess": set_header_values,
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

@frappe.whitelist()
def get_production_plans(customer):
    plans = frappe.get_all(
        "Production Plan",
        filters={
            "custom_customer_name": customer,
            "docstatus": 1
        },
        fields=["name"]
    )

    data = []

    for p in plans:
        doc = frappe.get_doc("Production Plan", p.name)

        for item in doc.po_items:  # FG Items table
            row = {
                "production_plan": doc.name,
                "item_code": item.item_code,
                "qty": item.planned_qty,
				"indent": doc.custom_indent
            }

            data.append(row)

    return data


@frappe.whitelist()
def get_custom_assembly_items(doc):
	if isinstance(doc, str):
		doc = frappe._dict(json.loads(doc))

	return _build_custom_assembly_items(doc)


@frappe.whitelist()
def recalculate_work_order_metrics(doc):
	"""Recalculate WO weight, area, and assembly rows from the current form state."""
	if isinstance(doc, str):
		doc = json.loads(doc)

	doc = frappe.get_doc(doc)
	return {
		"custom_wo_weight_": get_total_weight(doc),
		"custom_area": get_total_area(doc),
		"custom_assembly_item": _build_custom_assembly_items(doc),
	}


def _get_selected_item_bom(row):
	bom_no = _row_val(row, "bom_no")
	if not bom_no and _row_val(row, "item_code"):
		bom_no = frappe.db.get_value(
			"BOM",
			{"item": _row_val(row, "item_code"), "is_active": 1, "is_default": 1},
			"name",
		)
	return bom_no


def _selected_item_multiplier(row):
	multiplier = _row_val(row, "planned_qty")
	return multiplier if multiplier is not None else 1


def _row_val(row, fieldname, default=None):
	if isinstance(row, dict):
		return row.get(fieldname, default)
	return getattr(row, fieldname, default)


def _build_custom_assembly_items(doc):
	if isinstance(doc, str):
		# `doc` can be passed as either serialized json (from client)
		# or as a document name (from some hooks).
		try:
			doc = frappe._dict(json.loads(doc))
		except Exception:
			doc = frappe.get_doc("Production Plan", doc)

	assembly_map = {}

	def add_items_from_bom(bom_no, multiplier, drawing_no=None):
		if not bom_no:
			return

		bom = frappe.get_doc("BOM", bom_no)
		for bom_item in bom.items:
			# Keep only non-stock BOM items (matches earlier custom behavior)
			if bom_item.is_stock_item:
				continue

			# Respect real qty=0; default to 1 only when multiplier is missing/None.
			mult = multiplier if multiplier is not None else 1
			qty = flt(bom_item.qty) * flt(mult)
			if qty <= 0:
				continue

			if bom_item.item_code in assembly_map:
				assembly_map[bom_item.item_code]["qty"] += qty
			else:
				assembly_map[bom_item.item_code] = {
					"item_code": bom_item.item_code,
					# These fields will be fetched from Item master below.
					"item_name": "",
					"item_description": "",
					"uom": bom_item.uom or bom_item.stock_uom,
					"qty": qty,
					"area": 0,
					"weight_per_unit": 0,
					"thickness_in_mm": 0,
					"development_size_a": 0,
					"development_size_b": 0,
					"full_drawing_no": drawing_no or "",
					"item_group": "",
				}

	for row in doc.get("po_items", []):
		multiplier = row.get("planned_qty")
		add_items_from_bom(row.get("bom_no"), multiplier)

	for row in doc.get("sub_assembly_items", []):
		multiplier = row.get("qty")
		add_items_from_bom(row.get("bom_no"), multiplier)

	for row in doc.get("custom_selected_item") or []:
		add_items_from_bom(
			_get_selected_item_bom(row),
			_selected_item_multiplier(row),
			_row_val(row, "drawing_no"),
		)

	if assembly_map:
		item_meta = frappe.get_all(
			"Item",
			filters={"name": ["in", list(assembly_map.keys())]},
			fields=[
				"name",
				"item_name",
				"description",
				"item_group",
				"custom_full_drawing_number_",
				"custom_development_size_a",
				"custom_development_size_b",
				"custom_area",
				"weight_per_unit",
				"custom_t",
			],
		)

		for d in item_meta:
			row = assembly_map.get(d.name)
			if not row:
				continue
			row["item_name"] = d.item_name or row.get("item_name")
			row["item_description"] = d.description or row.get("item_description")
			row["item_group"] = d.item_group or ""
			row["full_drawing_no"] = d.custom_full_drawing_number_ or ""
			row["development_size_a"] = flt(d.custom_development_size_a)
			row["development_size_b"] = flt(d.custom_development_size_b)
			row["area"] = flt(d.custom_area)
			row["weight_per_unit"] = flt(d.weight_per_unit)
			row["thickness_in_mm"] = flt(d.custom_t)
			row["total_weight"] = flt(row.get("qty")) * flt(d.weight_per_unit)

	return list(assembly_map.values())


def populate_custom_assembly_items(doc, method=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("Production Plan", doc)

	rows = _build_custom_assembly_items(doc)
	doc.set("custom_assembly_item", [])
	for row in rows:
		doc.append("custom_assembly_item", row)

def get_total_weight(doc):
	"""Grand total weight — same logic as Thickness List print format."""
	allowed_groups = ["Specialised Item", "Standard Item"]
	total_wt = 0

	def process_bom(bom_no, multiplier):
		nonlocal total_wt

		if not bom_no:
			return

		bom = frappe.get_doc("BOM", bom_no)

		for item in bom.items:
			if item.custom_item_group not in allowed_groups:
				continue

			itm = frappe.get_cached_doc("Item", item.item_code)
			qty = flt(item.qty) * flt(multiplier if multiplier is not None else 1)
			total_wt += flt(itm.weight_per_unit) * qty

	for row in doc.get("po_items") or []:
		process_bom(row.bom_no, row.planned_qty)

	for row in doc.get("sub_assembly_items") or []:
		process_bom(_row_val(row, "bom_no"), _row_val(row, "qty"))

	for row in doc.get("custom_selected_item") or []:
		bom_no = _get_selected_item_bom(row)
		multiplier = _selected_item_multiplier(row)
		if bom_no:
			process_bom(bom_no, multiplier)
		elif _row_val(row, "item_code"):
			itm = frappe.get_cached_doc("Item", _row_val(row, "item_code"))
			qty = flt(multiplier if multiplier is not None else 1)
			total_wt += flt(itm.weight_per_unit) * qty

	return round(total_wt, 3)


def get_total_area(doc):
	"""Grand total area — same logic as Thickness List print format."""
	allowed_groups = ["Specialised Item", "Standard Item"]
	grand_area = 0

	def process_bom(bom_no, multiplier):
		nonlocal grand_area

		if not bom_no:
			return

		bom = frappe.get_doc("BOM", bom_no)

		for item in bom.items:
			if item.custom_item_group not in allowed_groups:
				continue

			itm = frappe.get_cached_doc("Item", item.item_code)
			qty = flt(item.qty) * flt(multiplier if multiplier is not None else 1)
			grand_area += flt(itm.custom_area) * qty

	for row in doc.get("po_items") or []:
		process_bom(row.bom_no, row.planned_qty)

	for row in doc.get("sub_assembly_items") or []:
		process_bom(_row_val(row, "bom_no"), _row_val(row, "qty"))

	for row in doc.get("custom_selected_item") or []:
		bom_no = _get_selected_item_bom(row)
		multiplier = _selected_item_multiplier(row)
		if bom_no:
			process_bom(bom_no, multiplier)
		elif _row_val(row, "item_code"):
			itm = frappe.get_cached_doc("Item", _row_val(row, "item_code"))
			qty = flt(multiplier if multiplier is not None else 1)
			grand_area += flt(itm.custom_area) * qty

	return round(grand_area, 4)


def get_work_order_group_key(work_order_name):
	"""Split work orders (WO26-023/1, WO26-023/5) share the same base key."""
	if not work_order_name:
		return work_order_name
	if "/" in work_order_name:
		return work_order_name.rsplit("/", 1)[0]
	return work_order_name


def get_wo_weight_and_area(work_order):
	if isinstance(work_order, str):
		work_order = frappe.get_doc("Production Plan", work_order)

	return flt(work_order.custom_wo_weight_), flt(work_order.custom_area)


def apply_work_order_metrics_to_ppt(ppt):
	"""Child rows use each WO's weight/area; parent totals each WO group once."""
	total_weight = 0
	total_area = 0
	seen_groups = set()

	for row in ppt.get("production_process_tracking_item") or []:
		wo_name = row.work_order_no if hasattr(row, "work_order_no") else row.get("work_order_no")
		if not wo_name:
			continue

		weight, area = get_wo_weight_and_area(wo_name)

		if hasattr(row, "weight_kg"):
			row.weight_kg = weight
			row.area_sq_mtr_paint = area
		else:
			row["weight_kg"] = weight
			row["area_sq_mtr_paint"] = area

		group_key = get_work_order_group_key(wo_name)
		if group_key in seen_groups:
			continue

		seen_groups.add(group_key)
		total_weight += weight
		total_area += area

	ppt.weight_kg = total_weight
	ppt.area_sq_mtr_paint = total_area

	return {"weight_kg": total_weight, "area_sq_mtr_paint": total_area}


def validate_production_plan_mr_links(doc, method=None):
	"""Require indent, po_items, and MR item link on every line (for correct naming & qty checks)."""
	_validate_production_plan_mr_links(doc)


def validate(self, method=None):
	_validate_production_plan_mr_links(self)
	populate_custom_assembly_items(self)
	self.custom_wo_weight_ = get_total_weight(self)
	self.custom_area = get_total_area(self)


def _validate_production_plan_mr_links(doc):
	title = _("Work Order")
	indent = cstr(doc.get("custom_indent")).strip()
	if not indent:
		frappe.throw(_("Indent (Material Request) is required."), title=title)
	if not frappe.db.exists("Material Request", indent):
		frappe.throw(_("Indent {0} is not a valid Material Request.").format(indent), title=title)

	if not doc.get("po_items"):
		frappe.throw(_("Add at least one finished-good item before saving."), title=title)

	for row in doc.po_items:
		if not row.item_code:
			frappe.throw(_("Row #{0}: Item is required.").format(row.idx), title=title)
		if flt(row.planned_qty) <= 0:
			frappe.throw(_("Row #{0}: Planned quantity must be greater than 0.").format(row.idx), title=title)

		mr = cstr(row.get("material_request")).strip()
		mri = cstr(row.get("material_request_item")).strip()
		if not mr:
			frappe.throw(
				_("Row #{0}: Material Request link is required on the item row.").format(row.idx),
				title=title,
			)
		if not mri:
			frappe.throw(
				_("Row #{0}: Material Request Item link is required on the item row.").format(row.idx),
				title=title,
			)
		if mr != indent:
			frappe.throw(
				_("Row #{0}: Material Request must match Indent {1}.").format(row.idx, indent),
				title=title,
			)
		if not frappe.db.exists("Material Request Item", mri):
			frappe.throw(_("Row #{0}: Invalid Material Request Item {1}.").format(row.idx, mri), title=title)
		mri_item = frappe.db.get_value("Material Request Item", mri, ["item_code", "parent"], as_dict=True)
		if not mri_item or mri_item.parent != indent:
			frappe.throw(
				_("Row #{0}: Material Request Item {1} does not belong to Indent {2}.").format(
					row.idx, mri, indent
				),
				title=title,
			)
		if cstr(mri_item.item_code).strip() != cstr(row.item_code).strip():
			frappe.throw(
				_("Row #{0}: Item {1} does not match Material Request line item {2}.").format(
					row.idx, row.item_code, mri_item.item_code
				),
				title=title,
			)


def autoname(doc, method=None):
	"""Name Production Plan (Work Order).

	Format: WO{YY}-{NNN} or WO{YY}-{NNN}/{S}

	- Same Material Request (custom_indent) shares one base (WO26-004).
	- Partial plan / split (MR still has pending qty) → suffix /1, /2, /3 …
	- First plan and full MR qty covered → WO26-004 (no suffix).
	"""
	_validate_production_plan_mr_links(doc)
	base_id = _get_or_make_work_order_base(doc)
	if not re.search(r"[A-Za-z0-9]", base_id):
		frappe.throw(_("Work order name base must contain letters or numbers."))

	if _use_split_suffix(doc, base_id):
		doc.name = f"{base_id}/{_get_next_suffix(doc, base_id)}"
	else:
		doc.name = base_id


def _use_split_suffix(doc, base_id):
	"""Suffix when MR has balance after this plan, or other plans already exist for the indent."""
	indent = cstr(doc.get("custom_indent")).strip()

	if frappe.db.exists("Production Plan", base_id):
		return True

	other_plans = frappe.db.count("Production Plan", {"custom_indent": indent})
	if other_plans:
		return True

	return _mr_has_balance_after_plan(doc)


def _this_plan_qty_by_mr_item(doc):
	qty_by_item = {}
	for row in doc.get("po_items") or []:
		mri = cstr(row.get("material_request_item")).strip()
		if not mri:
			continue
		qty_by_item[mri] = qty_by_item.get(mri, 0) + flt(row.get("planned_qty"))
	return qty_by_item


def _other_planned_qty(mr_name, mr_item_name, exclude_pp=None):
	"""Planned qty on other Production Plans (not cancelled), excluding current doc."""
	cond = ""
	params = [mr_name, mr_item_name]
	if exclude_pp and not cstr(exclude_pp).startswith("new-"):
		cond = "AND pp.name != %s"
		params.append(exclude_pp)

	row = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(ppi.planned_qty), 0)
		FROM `tabProduction Plan Item` ppi
		INNER JOIN `tabProduction Plan` pp ON pp.name = ppi.parent
		WHERE ppi.material_request = %s
			AND ppi.material_request_item = %s
			AND pp.docstatus != 2
			{cond}
		""",
		tuple(params),
	)[0][0]
	return flt(row)


def _mr_has_balance_after_plan(doc):
	"""True if any linked MR line still has pending qty after this plan."""
	this_plan = _this_plan_qty_by_mr_item(doc)
	mr_names = {cstr(r.material_request).strip() for r in doc.get("po_items") or [] if r.material_request}
	exclude = doc.name if doc.get("name") else None

	for mr_name in mr_names:
		mr = frappe.get_doc("Material Request", mr_name)
		for mr_item in mr.items:
			if not mr_item.item_code:
				continue
			mr_qty = flt(mr_item.qty)
			other = _other_planned_qty(mr_name, mr_item.name, exclude_pp=exclude)
			this_qty = this_plan.get(mr_item.name, 0)
			if mr_qty - other - this_qty > 0.0001:
				return True
	return False


def _wo_name_regex(prefix):
	"""WO26-001/1 or WO26-001 → group 1 = sequence 001."""
	return re.compile(rf"^{re.escape(prefix)}(\d{{3}})(?:/\d+)?$")


def _get_or_make_work_order_base(doc):
	"""WOYY-NNN from posting_date; one base per custom_indent."""
	date_value = doc.get("posting_date") or nowdate()
	yy = f"{getdate(date_value).year % 100:02d}"
	prefix = f"WO{yy}-"
	name_rx = _wo_name_regex(prefix)
	indent = cstr(doc.get("custom_indent")).strip()

	# Same indent → reuse base (WO26-004 or WO26-004/1 → WO26-004).
	if indent:
		for row in frappe.get_all(
			"Production Plan",
			filters={"custom_indent": indent, "name": ["like", f"{prefix}%"]},
			fields=["name"],
			order_by="creation asc",
			limit_page_length=0,
		):
			match = name_rx.match(cstr(row.name).strip())
			if match:
				return f"{prefix}{match.group(1)}"

	# New indent: next global sequence for this year.
	max_seq = 0
	for row in frappe.get_all(
		"Production Plan",
		filters={"name": ["like", f"{prefix}%"]},
		fields=["name"],
		limit_page_length=0,
	):
		match = name_rx.match(cstr(row.name).strip())
		if match:
			max_seq = max(max_seq, int(match.group(1)))

	return f"{prefix}{max_seq + 1:03d}"


def _get_next_suffix(doc, base_id):
	indent = cstr(doc.get("custom_indent")).strip()
	filters = {"name": ["like", f"{base_id}/%"]}
	if indent:
		filters["custom_indent"] = indent

	existing = frappe.get_all("Production Plan", filters=filters, fields=["name"], limit_page_length=0)
	max_suffix = _max_trailing_number(existing, "name", rf"^{re.escape(base_id)}/(\d+)$")

	next_suffix = max_suffix + 1
	while frappe.db.exists("Production Plan", f"{base_id}/{next_suffix}"):
		next_suffix += 1
	return next_suffix


def _max_trailing_number(rows, fieldname, pattern):
	regex = re.compile(pattern)
	max_value = 0
	for row in rows:
		match = regex.match(cstr(row.get(fieldname)).strip())
		if match:
			max_value = max(max_value, int(match.group(1)))
	return max_value