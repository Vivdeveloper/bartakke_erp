import frappe

@frappe.whitelist()
def get_mr(customer):
    return frappe.db.get_all(
        "Material Request",
        filters={
            "custom_customer_name": customer,
            "docstatus": 1
        },
        pluck="name"
    )


@frappe.whitelist()
def get_fg_item(customer, indent):
    indent = frappe.parse_json(indent) if indent else []

    if not indent:
        return {"items": []}

    items = frappe.db.get_all(
        "Material Request Item",
        filters={
            "parent": ["in", indent]
        },
        fields=[
            "item_code",
            "qty",
            "stock_uom as uom",
            "schedule_date",
            "warehouse"
        ]
    )
    for row in items:
        row["item_name"] = frappe.db.get_value(
            "Item",
            row["item_code"],
            "item_name"
        )

        row["rate"] = frappe.db.get_value(
            "Item Price",
            {'item_code':row["item_code"], 'selling': 1},
            "price_list_rate"
        )

        row["description"] = frappe.db.get_value(
            "Item",
            row["item_code"],
            "description"
        )

    return {"items": items}