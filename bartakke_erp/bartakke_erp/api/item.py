# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _

def validate(doc, method=None):
    item_drawing(doc)

def before_save(doc, method=None):
    create_drawing(doc)
    get_full_drawing_no(doc)

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

def create_drawing(doc):
    if not frappe.db.exists("Drawing", {'item_code': doc.get('name')}) and doc.get('custom_sf_code') and doc.get('custom_drawing_no'):
        name = f"{doc.get('custom_drawing_no')}"
        drawing = frappe.new_doc('Drawing')
        drawing.item_code = doc.get('name')
        drawing.item_name = doc.get('item_name')
        drawing.sf_code = doc.get('custom_sf_code')
        drawing.drawing_number = name
        drawing.item_group = doc.get("item_group")
        drawing.insert()


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

    if doc.get("custom_sf_code"):

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
                drawing_numbers = []
                for d in drawings:
                    if "-" in d:
                        try:
                            drawing_numbers.append(int(float(d.split("-", 1)[1])))
                        except ValueError:
                            continue

                next_number = max(drawing_numbers) + 1 if drawing_numbers else 1

            else:
                if frappe.db.exists("Drawing Configuration", doc.get("item_group")):
                    next_number = frappe.db.get_value(
                        "Drawing Configuration",
                        doc.get("item_group"),
                        "no_starts_from"
                    )
                else:
                    next_number = 1001

            return next_number


        if doc.get("custom_parent_item_group") == "Products":

            drawings = frappe.db.get_all(
                "Drawing",
                filters={"parent_group": doc.get("custom_parent_item_group")},
                pluck="name"
            )

            if drawings:
                drawing_numbers = []
                for d in drawings:
                    if "-" in d:
                        try:
                            drawing_numbers.append(int(float(d.split("-", 1)[1])))
                        except ValueError:
                            continue

                next_number = max(drawing_numbers) + 1 if drawing_numbers else 1001

            else:
                next_number = 1001

            return next_number

    return None


@frappe.whitelist()
def get_revision(doc):
    doc = json.loads(doc)
    if doc.get('custom_drawing_no') and doc.get('custom_sf_code'):
        name = f"{doc.get('custom_sf_code')}-{doc.get('custom_drawing_no')}"
        if frappe.db.exists("Drawing", name):
            drawing_doc = frappe.get_doc("Drawing", {'name': name, 'item_code': doc.get('item_code')})
            revis = [i.drawing_revision for i in drawing_doc.drawing_revision]
            revision = revis[-1]
            if revision.count('-') == 2:
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
    if doc.custom_parent_item_group not in ["Products", "Assembly Item"]:
        return

    parts = []

    if doc.custom_w:
        parts.append(f"{doc.custom_w} W")
    if doc.custom_d:
        parts.append(f"{doc.custom_d} D")
    if doc.custom_h:
        parts.append(f"{doc.custom_h} H")
    if doc.custom_t:
        parts.append(f"{doc.custom_t} T")

    if not parts:
        return

    dimensions = " x ".join(parts)
    base_name = f"{doc.item_name or 'Item'} {dimensions}"
    
    doc.name = base_name
    doc.item_name = base_name

@frappe.whitelist()
def add_revision111(file_url):
    if not file_url:
        frappe.throw(_("File is required"))

    file_name = frappe.db.get_value(
        "File",
        {"file_url": file_url},
        "name"
    )

    if not file_name:
        frappe.throw(_("Uploaded file not found. Please try again."))

    file_doc = frappe.get_doc("File", file_name)

    filename = file_doc.file_name.rsplit(".", 1)[0]

    if filename.count("-") < 1:
        frappe.throw(_("Invalid file name format"))

    drawing_name = filename

    if not frappe.db.exists("Drawing", drawing_name):
        frappe.throw(_("Drawing {0} not found").format(drawing_name))

    drawing_doc = frappe.get_doc("Drawing", drawing_name)

    revisions = [r.drawing_revision for r in drawing_doc.drawing_revision if r.drawing_revision]

    if len(revisions)>1:
        last_revision = revisions[-1]
        parts = last_revision.split("-")
        last_rev_no = int(parts[-1]) if parts[-1].isdigit() else 0
        next_rev = last_rev_no + 1
    else:
        next_rev = 1

    new_revision = f"{drawing_name}-{next_rev}"
    item = frappe.get_doc("Item", drawing_doc.item_code)
    item.custom_revision = f"{item.custom_drawing_no}-{next_rev}"
    item.save()

    drawing_doc.append("drawing_revision", {
        "drawing_revision": new_revision,
        "revision_time": frappe.utils.now(),
        "created_by": frappe.session.user,
        "attach": file_url
    })

    drawing_doc.save(ignore_permissions=True)

    return new_revision

def get_full_drawing_no(doc):
    if not (doc.custom_sf_code and doc.custom_drawing_no and doc.custom_sheet):
        return

    doc.custom_full_drawing_number_ = f"{doc.custom_sf_code}-{doc.custom_drawing_no}-{doc.custom_revision}/{doc.custom_sheet}"