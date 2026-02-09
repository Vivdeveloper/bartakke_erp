import frappe

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
