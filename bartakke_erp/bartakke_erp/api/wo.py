import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from bartakke_erp.bartakke_erp.api.production_plan import (
    apply_work_order_metrics_to_ppt,
    get_wo_weight_and_area,
)

@frappe.whitelist()
def get_wo(customer):
    return frappe.db.get_all(
        "Production Plan",
        filters={
            "custom_customer_name": customer,
            "docstatus": 1
        },
        pluck="name"
    )


@frappe.whitelist()
def get_fg_item(customer, wo):
    wo = frappe.parse_json(wo) if wo else []

    if not wo:
        return {"items": []}

    items = frappe.db.get_all(
        "Production Plan Item",
        filters={
            "parent": ["in", wo]
        },
        fields=[
            "item_code",
            "planned_qty as qty",
            "stock_uom as uom",
            "warehouse"
        ]
    )
    for row in items:
        row["item_name"] = frappe.db.get_value(
            "Item",
            row["item_code"],
            "item_name"
        )
        row["description"] = frappe.db.get_value(
            "Item",
            row["item_code"],
            "description"
        )
        row["rate"] = frappe.db.get_value(
            "Item Price",
            {'item_code':row["item_code"], 'selling': 1},
            "price_list_rate"
        )
        row['delivery_date'] = frappe.utils.today()

    return {"items": items}

@frappe.whitelist()
def create_production_process_tracking(source_name, target_doc=None):

    def set_header_values(source, target, source_parent=None):
        target.work_order_no = source.name
        target.indent_no = source.custom_indent
        target.indent_date = frappe.db.get_value(
            "Material Request",
            source.custom_indent,
            "transaction_date"
        )
        target.customer = source.custom_customer_name
        target.indent_received_date = frappe.db.get_value("Material Request", source.custom_indent, 'schedule_date')
        target.po_number = source.custom_customer_po_no
        target.customer_po_date = source.custom_customer_po_date
        target.delivery_date = source.custom_customer_delivery

        stages = frappe.db.get_all("Production Stages", pluck='name')

        target.set("production_stage_log", [])
        for stage in stages:
            target.append("production_stage_log", {
                "stage": stage
            })

    doc = get_mapped_doc(
        "Production Plan",
        source_name,
        {
            "Production Plan": {
                "doctype": "Production Process Tracking",
                "validation": {
                    "docstatus": ["=", 1]
                },
                "postprocess": set_header_values
            }
        },
        target_doc
    )

    return doc

@frappe.whitelist()
def get_assembly_item_details(work_order):
    frappe.log_error('get_area_wt')

    total_area = 0
    total_weight = 0

    wo = frappe.get_doc("Production Plan", work_order)

    planned_qty = frappe.db.get_value(
        "Production Plan Item",
        {"parent": work_order},
        "planned_qty"
    ) or 0

    for row in wo.custom_assembly_item:

        item_data = frappe.db.get_value(
            "Item",
            row.item_code,
            ["custom_area", "weight_per_unit"],
            as_dict=1
        ) or {}

        area = item_data.get("custom_area", 0)
        weight = item_data.get("weight_per_unit", 0)
        qty = row.qty or 0

        total_area += area * qty
        total_weight += weight * qty

    return {
        "total_area": total_area,
        "total_weight": total_weight,
        "qty": planned_qty
    }

@frappe.whitelist()
def create_production_tracking(work_orders):
    return _create_production_tracking(work_orders=work_orders, selected_items=None)


@frappe.whitelist()
def get_work_order_po_items(work_orders):
    work_orders = frappe.parse_json(work_orders) if work_orders else []
    if not work_orders:
        return []

    rows = frappe.get_all(
        "Production Plan Item",
        filters={"parent": ["in", work_orders]},
        fields=[
            "name",
            "parent as work_order_no",
            "idx",
            "item_code",
            "planned_qty",
            "stock_uom",
        ],
        order_by="parent asc, idx asc",
    )

    item_codes = [row.item_code for row in rows if row.get("item_code")]
    item_name_map = {}
    if item_codes:
        for item in frappe.get_all(
            "Item",
            filters={"name": ["in", list(set(item_codes))]},
            fields=["name", "item_name"],
        ):
            item_name_map[item.name] = item.item_name

    for row in rows:
        row["item_name"] = item_name_map.get(row.item_code) or row.item_code

    return rows


@frappe.whitelist()
def create_production_tracking_for_items(work_orders, selected_items):
    return _create_production_tracking(
        work_orders=work_orders,
        selected_items=selected_items,
    )


def _create_production_tracking(work_orders, selected_items):
    work_orders = frappe.parse_json(work_orders) if work_orders else []
    selected_items = frappe.parse_json(selected_items) if selected_items else None

    if not work_orders:
        frappe.throw(_("Please select at least one Work Order"))

    selected_map = {}
    if selected_items is not None:
        if not selected_items:
            frappe.throw(_("Please select at least one item to generate Lot"))

        valid_work_orders = set(work_orders)
        for row in selected_items:
            wo_name = row.get("work_order_no")
            row_name = row.get("production_plan_item")
            if not wo_name or not row_name:
                frappe.throw(_("Invalid item selection payload"))
            if wo_name not in valid_work_orders:
                frappe.throw(
                    _("Selected item {0} does not belong to selected Work Orders").format(
                        frappe.bold(row_name)
                    )
                )
            selected_map.setdefault(wo_name, set()).add(row_name)

    ppt = frappe.new_doc("Production Process Tracking")

    for wo_name in work_orders:
        wo = frappe.get_doc("Production Plan", wo_name)
        total_weight, total_area = get_wo_weight_and_area(wo)
        selected_rows_for_wo = selected_map.get(wo_name, set())
        valid_row_names = {row.name for row in wo.po_items}
        invalid_row_names = selected_rows_for_wo - valid_row_names
        if invalid_row_names:
            frappe.throw(
                _("Invalid selected item rows for Work Order {0}: {1}").format(
                    frappe.bold(wo_name),
                    ", ".join(sorted(invalid_row_names)),
                )
            )

        for item in wo.po_items:
            if selected_items is not None and item.name not in selected_rows_for_wo:
                continue

            ppt.append("production_process_tracking_item", {
                "item": item.item_code,
                "work_order_qty": item.planned_qty,
                "work_order_no": wo.name,
                "indent_date": frappe.db.get_value(
                    "Material Request",
                    wo.custom_indent,
                    "transaction_date"
                ),
                "indent_received_date": frappe.db.get_value(
                    "Material Request",
                    wo.custom_indent,
                    'schedule_date'
                ),
                "po_number": wo.custom_customer_po_no,
                "customer_po_date": wo.custom_customer_po_date,
                "delivery_date": wo.custom_customer_delivery,
                "weight_kg": total_weight,
                "area_sq_mtr_paint": total_area,
            })

        if not ppt.get("customer"):
            ppt.customer = wo.get("custom_customer_name")

    if not (ppt.get("production_process_tracking_item") or []):
        frappe.throw(_("No items available to generate Lot"))

    apply_work_order_metrics_to_ppt(ppt)

    stages = frappe.db.get_all("Production Stages", pluck='name')

    ppt.set("production_stage_log", [])
    for stage in stages:
        ppt.append("production_stage_log", {
            "stage": stage
        })

    ppt.insert(ignore_permissions=True)
    return ppt.name