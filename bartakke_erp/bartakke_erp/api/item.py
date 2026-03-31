# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
import re
from frappe.utils.file_manager import save_file


def validate(doc, method=None):
    item_drawing(doc)

def after_insert(doc, method=None):
    create_drawing(doc)

def before_save(doc, method=None):
    get_full_drawing_no(doc)
    rename_item(doc)

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
        drawing.drawing_number = doc.get('custom_drawing_no')
        drawing.item_group = doc.get("item_group")
        drawing.sheet = doc.get("custom_sheet")
        drawing.revision = doc.get("custom_revision")
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

    elif self.custom_full_drawing_number_:
        frappe.delete_doc(
                "Drawing",
                self.custom_full_drawing_number_,
                ignore_permissions=True,
                force=1
            )



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
            drawing_doc.latest_revision = f"{name}-{set_revision}"
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

def rename_item(doc):

    if doc.custom_parent_item_group not in ["Products", "Assembly Item"]:
        return

    # Get previous document
    old_doc = doc.get_doc_before_save()

    # If document is new, skip
    if not old_doc:
        return

    # Check if any dimension changed
    fields = ["custom_w", "custom_d", "custom_h", "custom_t"]

    changed = any(doc.get(f) != old_doc.get(f) for f in fields)

    if not changed:
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

    # Remove old dimensions
    base_name = re.sub(r"\s\d+(\.\d+)?\s[WDHT](\s*x\s*\d+(\.\d+)?\s[WDHT])*", "", doc.item_name).strip()

    new_name = f"{base_name} {dimensions}"

    if doc.name != new_name:
        frappe.rename_doc(
            "Item",
            doc.name,
            new_name,
            force=True
        )

    doc.item_name = new_name

@frappe.whitelist()
def add_revision111(file_url):

    if not file_url:
        frappe.throw(_("File is required"))

    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")

    if not file_name:
        frappe.throw(_("Uploaded file not found. Please try again."))

    file_doc = frappe.get_doc("File", file_name)

    filename = file_doc.file_name.rsplit(".", 1)[0]

    # filename itself is revision now
    if "-" not in filename:
        frappe.throw(_("Invalid revision file name format"))

    if filename.count("-") < 2:
        frappe.throw(_("Invalid file name format"))

    parts = filename.split("-")
    new_counter = parts[-1]

    if not new_counter.isdigit():
        frappe.throw(_("Revision counter must be numeric"))

    new_counter = int(new_counter)

    drawing_name = "-".join(parts[:-1])

    if not frappe.db.exists("Drawing", drawing_name):
        frappe.throw(_("Drawing {0} not found").format(drawing_name))

    drawing_doc = frappe.get_doc("Drawing", drawing_name)

    revisions = [
        r.drawing_revision
        for r in drawing_doc.drawing_revision
        if r.drawing_revision
    ]

    # get latest counter
    if revisions:
        last_revision = revisions[-1]
        if last_revision.count("-") == 2:
            last_counter = int(last_revision.split("-")[-1])
        else:
            last_counter = 0
    else:
        last_counter = 0

    # main validation
    if new_counter <= last_counter:
        frappe.throw(
            _("Revision counter must be greater than latest revision ({0})").format(last_counter)
        )

    new_revision = filename

    # update item revision
    frappe.db.set_value(
        "Item",
        drawing_doc.item_code,
        "custom_revision",
        new_revision
    )

    # update drawing
    drawing_doc.latest_revision = new_revision

    drawing_doc.append("drawing_revision", {
        "drawing_revision": new_revision,
        "revision_time": frappe.utils.now(),
        "created_by": frappe.session.user,
        "attach": file_url
    })

    drawing_doc.save(ignore_permissions=True)

    return new_revision

def get_full_drawing_no(doc):
    if not (doc.custom_sf_code and doc.custom_drawing_no):
        return
    
    if doc.custom_sheet:
        doc.custom_full_drawing_number_ = f"{doc.custom_sf_code}-{doc.custom_drawing_no}-{doc.custom_revision}/{doc.custom_sheet}"
    else:
        doc.custom_full_drawing_number_ = f"{doc.custom_sf_code}-{doc.custom_drawing_no}-{doc.custom_revision}"
        

@frappe.whitelist()
def map_local_revisions(files):
    files = frappe.parse_json(files)

    # Store revisions grouped by base drawing
    drawings_map = {}

    for f in files:
        file_name = f.get("name")
        file_url = f.get("url")

        if not file_name or not file_url:
            continue

        # Extract first revision (e.g., 11-10001-1 from "11-10001-1 (20-10001-3)")
        matches = re.findall(r"\b\d+-\d+-\d+\b", file_name)
        if not matches:
            continue

        revision_name = matches[0]

        # Extract base drawing (e.g., 11-10001)
        parts = revision_name.split("-")
        base_drawing = f"{parts[0]}-{parts[1]}"

        # Detect file type
        ext = file_name.split(".")[-1].lower().strip()

        if ext == "pdf":
            field = "file_url"
        elif ext == "dxf":
            field = "dxf_file_url"
        else:
            continue  # skip unsupported files

        # Group data
        drawings_map.setdefault(base_drawing, {})
        drawings_map[base_drawing].setdefault(revision_name, {})
        drawings_map[base_drawing][revision_name][field] = file_url

    for base_drawing, revisions in drawings_map.items():

        drawing = frappe.db.get_value(
            "Drawing",
            {"name": ["like", f"{base_drawing}%"]},
            "name"
        )

        if not drawing:
            continue

        doc = frappe.get_doc("Drawing", drawing)

        for revision_name, files_data in revisions.items():

            existing_row = None
            for row in doc.drawing_revision:
                if row.drawing_revision == revision_name:
                    existing_row = row
                    break

            if existing_row:
                for key, value in files_data.items():
                    setattr(existing_row, key, value)
            else:
                doc.append("drawing_revision", {
                    "drawing_revision": revision_name,
                    "created_by": frappe.session.user,
                    **files_data
                })

        doc.save(ignore_permissions=True)

        latest_revision = max(
            revisions.keys(),
            key=lambda x: int(x.split("-")[-1])
        )

        if doc.name != latest_revision:
            if not frappe.db.exists("Drawing", latest_revision):
                frappe.rename_doc("Drawing", doc.name, latest_revision)

frappe.db.commit()