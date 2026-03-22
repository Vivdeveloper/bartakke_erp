import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

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
        target.colour = source.custom_panel_outside_color
        target.panel_colour_inside = source.custom_panel_color
        target.base_colour = source.custom_base_color

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
    work_orders = frappe.parse_json(work_orders)

    ppt = frappe.new_doc("Production Process Tracking")

    for wo_name in work_orders:
        wo = frappe.get_doc("Production Plan", wo_name)

        total_area = 0
        total_weight = 0

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

        for item in wo.po_items:
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
                "colour": wo.custom_panel_outside_color,
                "panel_colour_inside": wo.custom_panel_color,
                "base_colour": wo.custom_base_color,
                "weight_kg": total_weight,
                "area_sq_mtr_paint": total_area,
            })

        if not ppt.get("customer"):
            ppt.customer = wo.get("custom_customer_name")

    stages = frappe.db.get_all("Production Stages", pluck='name')

    ppt.set("production_stage_log", [])
    for stage in stages:
        ppt.append("production_stage_log", {
            "stage": stage
        })

    ppt.insert(ignore_permissions=True)
    return ppt.name