import frappe
import json

@frappe.whitelist()
def update_assembly_items(doc):
    assembly_item = frappe._dict()
    doc = json.loads(doc)
    if doc.get('custom_bom_assembly_item'):
        for i in doc.get('custom_bom_assembly_item'):
            if i.get("item_code"):
                assembly_item[i.get("item_code")] = i.get("qty")

    return assembly_item

@frappe.whitelist()
def update_sub_assembly_items(doc):
    sub_assembly_item = frappe._dict()
    doc = json.loads(doc)
    if doc.get('custom_bom_sub_assembly_item'):
        for i in doc.get('custom_bom_sub_assembly_item'):
            if i.get("item_code"):
                sub_assembly_item[i.get("item_code")] = i.get("qty")

    return sub_assembly_item

@frappe.whitelist()
def update_hardware_items(doc):
    hardware_item = frappe._dict()
    doc = json.loads(doc)
    if doc.get('custom_bom_hardware_item'):
        for i in doc.get('custom_bom_hardware_item'):
            if i.get("item_code"):
                hardware_item[i.get("item_code")] = i.get("qty")

    return hardware_item