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

    total_area = 0
    total_weight = 0

    wo = frappe.get_doc("Production Plan", work_order)
    planned_qty = frappe.db.get_value("Production Plan Item", {'parent':work_order}, 'planned_qty')

    for item in wo.custom_assembly_item:
        area, weight = frappe.db.get_value(
            "Item",
            item.item_code,
            ["custom_area", "weight_per_unit"]
        ) or (0, 0)

        total_area += (area or 0) * (item.qty or 0)
        total_weight += (weight or 0) * (item.qty or 0)

    return {
        "total_area": total_area,
        "total_weight": total_weight,
        "qty": planned_qty
    }