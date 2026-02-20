# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
import json

def validate(doc, method=None):
    item_drawing(doc)

def item_drawing(doc):
    if not doc.custom_drawing_no:
        return

    drawing_item = frappe.db.get_value(
        "Drawing",
        f"{doc.custom_sf_code}-{doc.custom_drawing_no}",
        "item_name"
    )
    

    if drawing_item and drawing_item != doc.item_name:
        frappe.throw(
            "There cannot be the same Drawing mapped to different Items"
        )


def sync_store_item_from_item(doc, method=None):
    """Sync disabled field from Item to Store Item (2-way sync)"""
    # Skip if this update came from Store Item sync
    if getattr(frappe.flags, "in_store_item_sync", False):
        return

    store_item_name = getattr(doc, "custom_store_item", None)
    if not store_item_name:
        return

    if not frappe.db.exists("Store Item", store_item_name):
        return

    # Set flag to prevent infinite loop
    frappe.flags.in_item_sync = True
    try:
        # Only sync disabled field (2-way)
        frappe.db.set_value("Store Item", store_item_name,
                            "disabled", doc.disabled or 0)
        frappe.db.commit()
    finally:
        frappe.flags.in_item_sync = False


def on_trash(self, method=None):
    """Delete linked Store Item when Item is deleted"""

    if getattr(frappe.flags, "in_item_delete", False):
        return

    if self.custom_store_item:
        frappe.flags.in_item_delete = True
        try:
            frappe.delete_doc(
                "Store Item",
                self.custom_store_item,
                ignore_permissions=True,
                force=1
            )
        finally:
            frappe.flags.in_item_delete = False



@frappe.whitelist()
def get_drawing(doc):
    doc = json.loads(doc)
    if doc.get('custom_sf_code'):
        assembly_groups = frappe.db.get_all(
            "Item Group",
            filters={"parent_item_group": "Assembly Item"},
            pluck="name"
        )


        if doc.get("item_group") in assembly_groups:
            drawings = frappe.db.get_all(
                "Drawing",
                filters={"item_group": doc.get("item_group")},
                pluck="name"
            )

            if drawings:
                drawing_numbers = [
                    int(d.split("-", 1)[1])
                    for d in drawings
                    if "-" in d
                ]
                next_number = max(drawing_numbers) + 1
            else:
                if frappe.db.exists("Drawing Configuration", doc.get("item_group")):
                    next_number = frappe.db.get_value("Drawing Configuration", doc.get("item_group"), 'no_starts_from')
                # else:
                #     next_number = 1001

            drawing = frappe.new_doc('Drawing')
            drawing.item_code = doc.get('item_code')
            drawing.sf_code = doc.get('custom_sf_code')
            drawing.drawing_number = next_number
            drawing.item_group = doc.get("item_group")
            drawing.insert()

            return next_number
        
        if doc.get("custom_parent_item_group") == "Products":
            drawings = frappe.db.get_all(
                "Drawing",
                filters={"parent_group": doc.get("custom_parent_item_group")},
                pluck="name"
            )
            if drawings:
                drawing_numbers = [
                    int(d.split("-", 1)[1])
                    for d in drawings
                    if "-" in d
                ]
                next_number = max(drawing_numbers) + 1
            
            else: 
                next_number = 1001

            drawing = frappe.new_doc('Drawing')
            drawing.item_code = doc.get('item_code')
            drawing.sf_code = doc.get('custom_sf_code')
            drawing.drawing_number = next_number
            drawing.item_group = doc.get("item_group")
            drawing.insert()
            return next_number

    return None


@frappe.whitelist()
def get_revision(doc):
    doc = json.loads(doc)
    if doc.get('custom_drawing_no') and doc.get('custom_sf_code'):
        name = f"{doc.get('custom_sf_code')}-{doc.get('custom_drawing_no')}"
        if frappe.db.exists("Drawing", name):
            drawing_doc = frappe.get_doc("Drawing", name)
            revis = [i.drawing_revision for i in drawing_doc.drawing_revision]
            revision = revis[-1]
            if len(revision) > 1:
                rev = int(revision[-1])
                set_revision = rev + 1
            else:
                set_revision = 1
            drawing_doc.append("drawing_revision", {
                'drawing_revision': f"{name}-{set_revision}",
                'revision_time': frappe.utils.now(),
                'created_by': frappe.session.user
            })
            drawing_doc.save()
            return f"{doc.get('custom_drawing_no')}-{set_revision}"

def autoname(doc, method=None):
    if doc.custom_parent_item_group != "Products":
        return

    parts = [
        doc.item_name,
        doc.custom_w,
        doc.custom_d,
        doc.custom_h,
        doc.custom_t,
    ]

    parts = [str(p).strip() for p in parts if p]

    if parts:
        doc.name = " x ".join(parts)