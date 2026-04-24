import frappe
import json
from erpnext.manufacturing.doctype.bom.bom import get_children as original_get_children

@frappe.whitelist()
def get_items(doc):
    items = frappe._dict()
    doc = json.loads(doc)
    if doc.get('custom_bom_assembly_items'):
        for i in doc.get('custom_bom_assembly_items'):
            if i.get("item_code"):
                items[i.get("item_code")] = i.get("qty")

    if doc.get('custom_bom_sub_assembly_items'):
        for i in doc.get('custom_bom_sub_assembly_items'):
            if i.get("item_code"):
                items[i.get("item_code")] = i.get("qty")

    if doc.get('custom_bom_hardware_items'):
        for i in doc.get('custom_bom_hardware_items'):
            if i.get("item_code"):
                items[i.get("item_code")] = i.get("qty")

    return items

@frappe.whitelist()
def get_children(parent=None, is_root=False, **filters):
    if not parent or parent == "BOM":
        if not filters.get("bom"):
            frappe.msgprint("Please select a BOM")
            return []

        parent = filters.get("bom")

    frappe.form_dict.parent = parent

    if frappe.form_dict.parent:
        bom_doc = frappe.get_cached_doc("BOM", frappe.form_dict.parent)
        frappe.has_permission("BOM", doc=bom_doc, throw=True)

        bom_items = frappe.get_all(
            "BOM Item",
            fields=["item_code", "bom_no as value", "stock_qty", "qty"],
            filters=[["parent", "=", frappe.form_dict.parent]],
            order_by="idx",
        )

        item_names = tuple(d.get("item_code") for d in bom_items)

        items = frappe.get_list(
            "Item",
            fields=[
                "image",
                "description",
                "name",
                "stock_uom",
                "item_name",
                "is_sub_contracted_item",
            ],
            filters=[["name", "in", item_names]],
        )

        for bom_item in bom_items:

            # merge item data
            bom_item.update(
                next(item for item in items if item.get("name") == bom_item.get("item_code"))
            )

            bom_item.parent_bom_qty = bom_doc.quantity
            bom_item.expandable = 0 if bom_item.value in ("", None) else 1
            bom_item.image = frappe.db.escape(bom_item.image)

            bom_item["custom_incomplete"] = 0

            if parent:
                bom_item["custom_incomplete"] = frappe.db.get_value(
                    "BOM",
                    parent,
                    "custom_incomplete"
                ) or 0

        return bom_items