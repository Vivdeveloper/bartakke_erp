# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
import re
from frappe.utils import cstr
from frappe.utils.file_manager import save_file


def _item_full_drawing_number(doc):
    """Same pattern as Drawing name: {sf}-{drawing_no}-{revision} or .../{sheet}."""
    sf = cstr(doc.get("custom_sf_code") or "").strip()
    dn = cstr(doc.get("custom_drawing_no") or "").strip()
    rev = cstr(doc.get("custom_revision") or "").strip()
    sheet = cstr(doc.get("custom_sheet") or "").strip()
    if not sf or not dn:
        return ""
    base = f"{sf}-{dn}-{rev}"
    return f"{base}/{sheet}" if sheet else base


def validate(doc, method=None):
    item_drawing(doc)

def after_insert(doc, method=None):
    create_drawing(doc)
    get_full_drawing_no(doc)


def before_save(doc, method=None):
    get_full_drawing_no(doc)
    if not doc.is_new():
        ensure_drawing_for_item(doc)
        get_full_drawing_no(doc)
    rename_item(doc)

def item_drawing(doc):
    """If custom_sf_code + custom_drawing_no are set: check Drawing by pair and other Item by pair; report all conflicts."""
    sf = cstr(doc.get("custom_sf_code") or "").strip()
    dn = cstr(doc.get("custom_drawing_no") or "").strip()
    if not sf or not dn:
        return

    item_code = doc.get("name")
    if not item_code:
        return

    errors = []

    row = frappe.db.get_value(
        "Drawing",
        {"sf_code": sf, "drawing_number": dn},
        ["name", "item_code"],
        as_dict=True,
    )
    if row and row.get("item_code") and row.get("item_code") != item_code:
        errors.append(
            _(
                "A Drawing ({0}) already exists for SF Code {1} and Drawing Number {2}, linked to Item {3}."
            ).format(
                frappe.bold(row.get("name")),
                frappe.bold(sf),
                frappe.bold(dn),
                frappe.bold(row.get("item_code")),
            )
        )

    other_item = frappe.db.get_value(
        "Item",
        {
            "name": ["!=", item_code],
            "custom_sf_code": sf,
            "custom_drawing_no": dn,
        },
        "name",
    )
    if other_item and not (row and row.get("item_code") == other_item):
        errors.append(
            _("Another Item ({0}) already uses SF Code {1} and Drawing Number {2}.").format(
                frappe.bold(other_item), frappe.bold(sf), frappe.bold(dn)
            )
        )

    if errors:
        frappe.throw(
            "\n\n".join(errors),
            title=_("Duplicate SF Code / Drawing Number"),
        )

def create_drawing(doc):
    if not frappe.db.exists("Drawing", {'item_code': doc.get('name')}) and doc.get('custom_sf_code') and doc.get('custom_drawing_no'):
        drawing = frappe.new_doc('Drawing')
        drawing.item_code = doc.get('name')
        drawing.item_name = doc.get('item_name')
        drawing.sf_code = doc.get('custom_sf_code')
        drawing.drawing_number = doc.get('custom_drawing_no')
        drawing.item_group = doc.get("item_group")
        drawing.sheet = doc.get("custom_sheet")
        drawing.revision = doc.get("custom_revision")
        drawing.insert()
        frappe.db.set_value(
            "Item",
            doc.get("name"),
            "custom_full_drawing_number_",
            drawing.name,
            update_modified=False,
        )
        if hasattr(doc, "custom_full_drawing_number_"):
            doc.custom_full_drawing_number_ = drawing.name


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
    new_rev = ''
    doc = json.loads(doc)

    if not frappe.db.exists("Drawing", {'item_code': doc.get('item_code')}):
        create_drawing(doc)
        return

    drawing_doc = frappe.get_doc("Drawing", {'item_code': doc.get('item_code')})

    old_revision = drawing_doc.revision
    new_revision = doc.get("custom_revision")

    def is_greater(new, old):
        try:
            return int(new) > int(old)
        except:
            return str(new) > str(old)

    if new_revision and (not old_revision or is_greater(new_revision, old_revision)):

        drawing_doc.revision = new_revision

        # Build new_rev from UPDATED doc
        if drawing_doc.get('sf_code'):
            new_rev += drawing_doc.get('sf_code')
        if drawing_doc.get('drawing_number'):
            new_rev += f"-{drawing_doc.get('drawing_number')}"
        if drawing_doc.get('revision'):
            new_rev += f"-{drawing_doc.get('revision')}"
        if drawing_doc.get('sheet'):
            new_rev += f"/{drawing_doc.get('sheet')}"

        drawing_doc.append("drawing_revision", {
            'drawing_revision': new_rev,
            'revision_time': frappe.utils.now(),
            'created_by': frappe.session.user
        })

        drawing_doc.latest_revision = new_rev
        drawing_doc.save()

        if drawing_doc.name != new_rev:
            if frappe.db.exists("Drawing", new_rev):
                frappe.throw(f"Drawing {new_rev} already exists")

            frappe.rename_doc("Drawing", drawing_doc.name, new_rev, force=True)

        dname = frappe.db.get_value("Drawing", {"item_code": doc.get("item_code")}, "name")
        if dname:
            frappe.db.set_value(
                "Item",
                doc.get("item_code"),
                "custom_full_drawing_number_",
                dname,
                update_modified=False,
            )

    return new_revision

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

    # Rebuild name when dimensions OR item_name (description) changed
    fields = ["custom_w", "custom_d", "custom_h", "custom_t"]
    dimension_changed = any(doc.get(f) != old_doc.get(f) for f in fields)
    item_name_changed = str(doc.item_name or "") != str(old_doc.item_name or "")

    if not dimension_changed and not item_name_changed:
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
    base_name = re.sub(r"\s\d+(\.\d+)?\s[WDHT](\s*x\s*\d+(\.\d+)?\s[WDHT])*", "", doc.item_name or "").strip()

    new_name = f"{base_name} {dimensions}"

    if doc.name != new_name:
        old_name = doc.name
        frappe.rename_doc(
            "Item",
            old_name,
            new_name,
            force=True,
        )
        doc.name = new_name
        # Desk expects `localname` (old id) + `name` (new id) on the saved doc so
        # frappe.model.sync → rename_after_save → "rename" → Form.rename_notify → set_route.
        doc.localname = old_name

    doc.item_name = new_name
    new_doc = frappe.get_doc("Item", new_name)

    # update latest values
    new_doc.custom_w = doc.custom_w
    new_doc.custom_d = doc.custom_d
    new_doc.custom_h = doc.custom_h
    new_doc.custom_t = doc.custom_t
    new_doc.item_name = new_name

    new_doc.flags.ignore_validate = True
    new_doc.save()
    if doc.default_bom:
        clean_name = re.sub(r"\.+", "", new_name)
        clean_name = clean_name.strip()
        bom = f"BOM-{clean_name}"
        frappe.rename_doc("BOM", doc.default_bom, bom, force=True)
        frappe.db.set_value("BOM", bom, 'item_name', new_name)
        new_doc.default_bom = bom
        new_doc.flags.ignore_validate = True
        new_doc.save()
        # Same in-memory doc is validated and written after before_save; without this,
        # doc.default_bom still points at the pre-rename BOM id → LinkValidationError
        # ("Could not find Default BOM: BOM-(old)…") after the BOM row was renamed.
        doc.default_bom = bom

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
    """Set Item.custom_full_drawing_number_ from Item fields. If a Drawing is linked, do not overwrite from Drawing.name when values disagree — throw instead."""
    if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_patch:
        return

    item_code = doc.get("name")
    full = _item_full_drawing_number(doc)

    if item_code:
        linked = frappe.db.get_value("Drawing", {"item_code": item_code}, "name")
        if linked:
            if not full:
                frappe.throw(
                    _(
                        "This Item is linked to Drawing {0}. Set Custom SF Code and Custom Drawing No. "
                        "(and revision/sheet if used) so they match that Drawing."
                    ).format(frappe.bold(linked)),
                    title=_("Drawing / Item mismatch"),
                )
            if full != linked:
                frappe.throw(
                    _(
                        "This Item is linked to Drawing {0}, but the Item fields build {1}. "
                        "Correct Custom SF Code, Drawing No., Revision, and Sheet to match the Drawing "
                        "(do not rely on auto-updating Full Drawing No.)."
                    ).format(frappe.bold(linked), frappe.bold(full)),
                    title=_("Drawing / Item mismatch"),
                )
            doc.custom_full_drawing_number_ = full
            return

    if full:
        doc.custom_full_drawing_number_ = full


def ensure_drawing_for_item(doc):
    """Create Drawing on Item update when SF + drawing no. are set but no Drawing yet (after_insert only runs on new Items)."""
    if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_patch:
        return
    if not doc.get("custom_sf_code") or not doc.get("custom_drawing_no"):
        return
    if frappe.db.exists("Drawing", {"item_code": doc.get("name")}):
        return
    create_drawing(doc)


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