import frappe
from frappe import _
import json
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, ceil
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.get_item_details import get_conversion_factor
from collections import defaultdict
from erpnext.manufacturing.doctype.production_plan.production_plan import (
	get_warehouse_list, get_raw_materials_of_sub_assembly_items, get_exploded_items, get_subitems, get_uom_conversion_factor, get_bin_details, get_materials_from_other_locations
)
from erpnext.manufacturing.doctype.production_plan.production_plan import ProductionPlan, get_sub_assembly_items

set_sub_assembly_items_based_on_level = ProductionPlan.set_sub_assembly_items_based_on_level
set_default_supplier_for_subcontracting_order = ProductionPlan.set_default_supplier_for_subcontracting_order
combine_subassembly_items = ProductionPlan.combine_subassembly_items

def get_sub_assembly_items2(doc, method=None):
	if len(doc.sub_assembly_items) == 0:
		get_sub_assembly_items1(doc)

def get_sub_assembly_items1(self, manufacturing_type=None):
	"Fetch sub assembly items and optionally combine them."
	self.sub_assembly_items = []
	sub_assembly_items_store = []  # temporary store to process all subassembly items
	bin_details = frappe._dict()

	for row in self.po_items:
		if self.skip_available_sub_assembly_item and not self.sub_assembly_warehouse:
			frappe.throw(_("Row #{0}: Please select the Sub Assembly Warehouse").format(row.idx))

		if not row.item_code:
			frappe.throw(_("Row #{0}: Please select Item Code in Assembly Items").format(row.idx))

		if not row.bom_no:
			frappe.throw(_("Row #{0}: Please select the BOM No in Assembly Items").format(row.idx))

		bom_data = []

		get_sub_assembly_items(
			[item.production_item for item in sub_assembly_items_store],
			bin_details,
			row.bom_no,
			bom_data,
			row.planned_qty,
			self.company,
			warehouse=self.sub_assembly_warehouse,
			skip_available_sub_assembly_item=self.skip_available_sub_assembly_item,
		)
		self.set_sub_assembly_items_based_on_level(row, bom_data, manufacturing_type)
		sub_assembly_items_store.extend(bom_data)

	if not sub_assembly_items_store and self.skip_available_sub_assembly_item:
		message = (
			_(
				"As there are sufficient Sub Assembly Items, Work Order is not required for Warehouse {0}."
			).format(self.sub_assembly_warehouse)
			+ "<br><br>"
		)
		message += _(
			"If you still want to proceed, please disable 'Skip Available Sub Assembly Items' checkbox."
		)

		frappe.msgprint(message, title=_("Note"))

	if self.combine_sub_items:
		# Combine subassembly items
		sub_assembly_items_store = self.combine_subassembly_items(sub_assembly_items_store)

	for idx, row in enumerate(sub_assembly_items_store):
		row.idx = idx + 1
		self.append("sub_assembly_items", row)

	self.set_default_supplier_for_subcontracting_order()


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

def get_material_request_items(
	doc,
	row,
	sales_order,
	company,
	ignore_existing_ordered_qty,
	include_safety_stock,
	warehouse,
	bin_dict,
	consumed_qty,
):
	required_qty = 0
	item_code = row.get("item_code")
	purchase_item = frappe.db.get_value("Item", row.get("item_code"), 'is_purchase_item')

	if ignore_existing_ordered_qty or bin_dict.get("projected_qty", 0) < 0:
		required_qty = flt(row.get("qty"))
	else:
		key = (item_code, warehouse)
		available_qty = flt(bin_dict.get("projected_qty", 0)) - consumed_qty[key]
		if available_qty > 0:
			required_qty = max(0, flt(row.get("qty")) - available_qty)
			consumed_qty[key] += min(flt(row.get("qty")), available_qty)
		else:
			required_qty = flt(row.get("qty"))

	if doc.get("consider_minimum_order_qty") and required_qty > 0 and required_qty < row["min_order_qty"]:
		required_qty = row["min_order_qty"]

	item_group_defaults = get_item_group_defaults(row.item_code, company)

	if not row["purchase_uom"]:
		row["purchase_uom"] = row["stock_uom"]

	if row["purchase_uom"] != row["stock_uom"]:
		if not (row["conversion_factor"] or frappe.flags.show_qty_in_stock_uom):
			frappe.throw(
				_("UOM Conversion factor ({0} -> {1}) not found for item: {2}").format(
					row["purchase_uom"], row["stock_uom"], row.item_code
				)
			)

			required_qty = required_qty / row["conversion_factor"]

	if frappe.db.get_value("UOM", row["purchase_uom"], "must_be_whole_number"):
		required_qty = ceil(required_qty)

	if include_safety_stock:
		required_qty += flt(row["safety_stock"])

	item_details = frappe.get_cached_value("Item", row.item_code, ["purchase_uom", "stock_uom"], as_dict=1)

	conversion_factor = 1.0
	if (
		row.get("default_material_request_type") == "Purchase"
		and item_details.purchase_uom
		and item_details.purchase_uom != item_details.stock_uom
	):
		conversion_factor = (
			get_conversion_factor(row.item_code, item_details.purchase_uom).get("conversion_factor") or 1.0
		)

	if required_qty > 0 and purchase_item == 1:
		return {
			"item_code": row.item_code,
			"item_name": row.item_name,
			"quantity": required_qty / conversion_factor,
			"conversion_factor": conversion_factor,
			"required_bom_qty": row.get("qty"),
			"stock_uom": row.get("stock_uom"),
			"warehouse": warehouse
			or row.get("source_warehouse")
			or row.get("default_warehouse")
			or item_group_defaults.get("default_warehouse"),
			"safety_stock": row.safety_stock,
			"actual_qty": bin_dict.get("actual_qty", 0),
			"projected_qty": bin_dict.get("projected_qty", 0),
			"ordered_qty": bin_dict.get("ordered_qty", 0),
			"reserved_qty_for_production": bin_dict.get("reserved_qty_for_production", 0),
			"min_order_qty": row["min_order_qty"],
			"material_request_type": row.get("default_material_request_type"),
			"sales_order": sales_order,
			"description": row.get("description"),
			"uom": row.get("purchase_uom") or row.get("stock_uom"),
			"main_bom_item": row.get("main_bom_item"),
		}

@frappe.whitelist()
def custom_get_items_for_material_requests(doc, warehouses=None, get_parent_warehouse_data=None):
	if isinstance(doc, str):
		doc = frappe._dict(json.loads(doc))

	if warehouses:
		warehouses = list(set(get_warehouse_list(warehouses)))

		if (
			doc.get("for_warehouse")
			and not get_parent_warehouse_data
			and doc.get("for_warehouse") in warehouses
		):
			warehouses.remove(doc.get("for_warehouse"))

	doc["mr_items"] = []

	po_items = doc.get("po_items") if doc.get("po_items") else doc.get("items")

	if doc.get("sub_assembly_items"):
		for sa_row in doc.sub_assembly_items:
			sa_row = frappe._dict(sa_row)
			if sa_row.type_of_manufacturing == "Material Request":
				po_items.append(
					frappe._dict(
						{
							"item_code": sa_row.production_item,
							"required_qty": sa_row.qty,
							"include_exploded_items": 0,
						}
					)
				)

	# Check for empty table or empty rows
	if not po_items or not [row.get("item_code") for row in po_items if row.get("item_code")]:
		frappe.throw(
			_("Items to Manufacture are required to pull the Raw Materials associated with it."),
			title=_("Items Required"),
		)

	company = doc.get("company")
	ignore_existing_ordered_qty = doc.get("ignore_existing_ordered_qty")
	include_safety_stock = doc.get("include_safety_stock")

	so_item_details = frappe._dict()
	existing_sub_assembly_items = set()

	sub_assembly_items = defaultdict(int)
	if doc.get("skip_available_sub_assembly_item") and doc.get("sub_assembly_items"):
		for d in doc.get("sub_assembly_items"):
			sub_assembly_items[(d.get("production_item"), d.get("bom_no"))] += d.get("qty")

	for data in po_items:
		if not data.get("include_exploded_items") and doc.get("sub_assembly_items"):
			data["include_exploded_items"] = 1

		planned_qty = data.get("required_qty") or data.get("planned_qty")
		ignore_existing_ordered_qty = data.get("ignore_existing_ordered_qty") or ignore_existing_ordered_qty
		warehouse = doc.get("for_warehouse")

		item_details = {}
		if data.get("bom") or data.get("bom_no"):
			if data.get("required_qty"):
				bom_no = data.get("bom")
				include_non_stock_items = 1
				include_subcontracted_items = 1 if data.get("include_exploded_items") else 0
			else:
				bom_no = data.get("bom_no")
				include_subcontracted_items = doc.get("include_subcontracted_items")
				include_non_stock_items = doc.get("include_non_stock_items")

			if not planned_qty:
				frappe.throw(_("For row {0}: Enter Planned Qty").format(data.get("idx")))

			if bom_no:
				if data.get("include_exploded_items") and doc.get("skip_available_sub_assembly_item"):
					item_details = {}
					if doc.get("sub_assembly_items"):
						item_details = get_raw_materials_of_sub_assembly_items(
							existing_sub_assembly_items,
							item_details,
							company,
							bom_no,
							include_non_stock_items,
							sub_assembly_items,
							planned_qty=planned_qty,
						)

				elif data.get("include_exploded_items") and include_subcontracted_items:
					# fetch exploded items from BOM
					item_details = get_exploded_items(
						item_details,
						company,
						bom_no,
						include_non_stock_items,
						planned_qty=planned_qty,
						doc=doc,
					)
				else:
					item_details = get_subitems(
						doc,
						data,
						item_details,
						bom_no,
						company,
						include_non_stock_items,
						include_subcontracted_items,
						1,
						planned_qty=planned_qty,
					)
		elif data.get("item_code"):
			item_master = frappe.get_doc("Item", data["item_code"]).as_dict()
			purchase_uom = item_master.purchase_uom or item_master.stock_uom
			conversion_factor = (
				get_uom_conversion_factor(item_master.name, purchase_uom) if item_master.purchase_uom else 1.0
			)

			item_details[item_master.name] = frappe._dict(
				{
					"item_name": item_master.item_name,
					"default_bom": doc.bom,
					"purchase_uom": purchase_uom,
					"default_warehouse": item_master.default_warehouse,
					"min_order_qty": item_master.min_order_qty,
					"default_material_request_type": item_master.default_material_request_type,
					"qty": planned_qty or 1,
					"is_sub_contracted": item_master.is_sub_contracted_item,
					"item_code": item_master.name,
					"description": item_master.description,
					"stock_uom": item_master.stock_uom,
					"conversion_factor": conversion_factor,
					"safety_stock": item_master.safety_stock,
				}
			)

		sales_order = data.get("sales_order")

		for item_code, details in item_details.items():
			so_item_details.setdefault(sales_order, frappe._dict())
			if item_code in so_item_details.get(sales_order, {}):
				so_item_details[sales_order][item_code]["qty"] = so_item_details[sales_order][item_code].get(
					"qty", 0
				) + flt(details.qty)
			else:
				so_item_details[sales_order][item_code] = details

	mr_items = []
	consumed_qty = defaultdict(float)

	for sales_order in so_item_details:
		item_dict = so_item_details[sales_order]
		for details in item_dict.values():
			warehouse = warehouse or details.get("source_warehouse") or details.get("default_warehouse")
			bin_dict = get_bin_details(details, doc.company, warehouse)
			bin_dict = bin_dict[0] if bin_dict else {}

			if details.qty > 0:
				items = get_material_request_items(
					doc,
					details,
					sales_order,
					company,
					ignore_existing_ordered_qty,
					include_safety_stock,
					warehouse,
					bin_dict,
					consumed_qty,
				)
				if items:
					mr_items.append(items)

	if (not ignore_existing_ordered_qty or get_parent_warehouse_data) and warehouses:
		new_mr_items = []
		for item in mr_items:
			get_materials_from_other_locations(item, warehouses, new_mr_items, company)

		mr_items = new_mr_items

	if not mr_items:
		to_enable = frappe.bold(_("Ignore Existing Projected Quantity"))
		warehouse = frappe.bold(doc.get("for_warehouse"))
		message = (
			_(
				"As there are sufficient raw materials, Material Request is not required for Warehouse {0}."
			).format(warehouse)
			+ "<br><br>"
		)
		message += _("If you still want to proceed, please enable {0}.").format(to_enable)

		frappe.msgprint(message, title=_("Note"))

	return mr_items

@frappe.whitelist()
def add_assembly_items(pp_name, items):

    if isinstance(items, str):
        items = json.loads(items)

    assembly_map = {}

    for item_data in items:

        bom_no = item_data.get("bom_no")
        if not bom_no:
            continue

        bom = frappe.get_doc("BOM", bom_no)
        if not bom.exploded_items:
            continue

        required_qty = item_data.get("qty", 1)

        item_codes = [d.item_code for d in bom.exploded_items]

        item_groups = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=[
                "name",
                "custom_parent_item_group",
                "custom_full_drawing_number_",
                "custom_development_size_a",
                "custom_development_size_b",
                "custom_area",
                "weight_per_unit",
                "custom_t",
                "item_group"
            ]
        )

        group_map = {d.name: d for d in item_groups}

        for exploded in bom.exploded_items:

            item_info = group_map.get(exploded.item_code)

            if not item_info:
                continue

            if item_info.custom_parent_item_group == "Assembly Item":

                qty = exploded.stock_qty * required_qty

                if exploded.item_code in assembly_map:
                    assembly_map[exploded.item_code]["qty"] += qty
                else:
                    assembly_map[exploded.item_code] = {
                        "item_code": exploded.item_code,
                        "item_name": exploded.item_name,
                        "item_description": exploded.description,
                        "uom": exploded.stock_uom,
                        "qty": qty,
                        "full_drawing_no": item_info.custom_full_drawing_number_,
                        "development_size_a": item_info.custom_development_size_a,
                        "development_size_b": item_info.custom_development_size_b,
                        "area": item_info.custom_area,
                        "weight_per_unit": item_info.weight_per_unit,
                        "thickness_in_mm": item_info.custom_t,
                        "item_group": item_info.item_group
                    }

    return list(assembly_map.values())