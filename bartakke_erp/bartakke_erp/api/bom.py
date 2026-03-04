import frappe
import json

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