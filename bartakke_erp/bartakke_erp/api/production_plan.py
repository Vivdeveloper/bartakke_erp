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


def _build_custom_assembly_items(doc):
	if isinstance(doc, str):
		# `doc` can be passed as either serialized json (from client)
		# or as a document name (from some hooks).
		try:
			doc = frappe._dict(json.loads(doc))
		except Exception:
			doc = frappe.get_doc("Production Plan", doc)

	assembly_map = {}

	def add_items_from_bom(bom_no, multiplier):
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
					"full_drawing_no": "",
					"item_group": "",
				}

	for row in doc.get("po_items", []):
		multiplier = row.get("planned_qty")
		add_items_from_bom(row.get("bom_no"), multiplier)

	for row in doc.get("sub_assembly_items", []):
		multiplier = row.get("qty")
		add_items_from_bom(row.get("bom_no"), multiplier)

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
    allowed_groups = ["Specialised Item", "Standard Item"]
    total_wt = 0

    def process_bom(bom_no, multiplier):
        nonlocal total_wt

        if not bom_no:
            return

        bom = frappe.get_doc("BOM", bom_no)

        for item in bom.items:
            if item.custom_item_group in allowed_groups:
                itm = frappe.get_cached_doc("Item", item.item_code)

                qty = flt(item.qty) * flt(multiplier or 1)
                total_wt += flt(itm.weight_per_unit) * qty

    for row in doc.po_items:
        process_bom(row.bom_no, row.planned_qty)

    return round(total_wt, 2)


def validate(self, method=None):
	populate_custom_assembly_items(self)
	total_wt = 0
	for row in self.get("custom_assembly_item") or []:
		# Ensure row.total_weight is set even if schema/data changes.
		row_total = flt(getattr(row, "total_weight", None))
		if not row_total:
			row_total = flt(row.get("qty")) * flt(row.get("weight_per_unit"))
			if hasattr(row, "total_weight"):
				row.total_weight = row_total
		total_wt += row_total

	self.custom_wo_weight_ = total_wt


def autoname(doc, method=None):
	"""Name format: WO26-001/1, WO26-001/2 (same indent => same base)."""
	base_id = _get_or_make_work_order_base(doc, cstr(doc.get("custom_work_order_id")).strip())
	if not re.search(r"[A-Za-z0-9]", base_id):
		frappe.throw(_("Custom Work Order ID must contain letters or numbers for naming."))

	# Keep custom_work_order_id field value untouched; use base_id only for naming.
	doc.name = f"{base_id}/{_get_next_suffix(doc, base_id)}"


def _get_or_make_work_order_base(doc, custom_work_order_id):
	"""Return base work order id in WOYY-NNN format."""
	if custom_work_order_id:
		# Accept either base `WO26-001` or full `WO26-001/1` as input.
		parsed = re.match(r"^(.*?)(?:/(\d+))?$", custom_work_order_id.rstrip("/"))
		return (parsed.group(1) if parsed else custom_work_order_id).strip()

	date_value = doc.get("posting_date") or nowdate()
	yy = f"{getdate(date_value).year % 100:02d}"
	prefix = f"WO{yy}-"
	indent = cstr(doc.get("custom_indent")).strip()

	# For the same indent, reuse the same base id and only increase `/N`.
	if indent:
		existing_for_indent = frappe.get_all(
			"Production Plan",
			filters={
				"custom_indent": indent,
				"custom_work_order_id": ["like", f"{prefix}%"],
			},
			fields=["custom_work_order_id"],
			order_by="creation desc",
			limit=1,
		)
		if existing_for_indent:
			return cstr(existing_for_indent[0].custom_work_order_id).strip()

	existing = frappe.get_all(
		"Production Plan",
		filters={"custom_work_order_id": ["like", f"{prefix}%"]},
		fields=["custom_work_order_id"],
		limit_page_length=0,
	)
	max_seq = _max_trailing_number(existing, "custom_work_order_id", rf"^{re.escape(prefix)}(\d+)$")
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