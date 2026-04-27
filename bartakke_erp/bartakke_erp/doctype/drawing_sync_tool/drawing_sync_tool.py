# Copyright (c) 2026

import frappe
import os
import re
from urllib.parse import urlparse
from frappe.model.document import Document


class DrawingSyncTool(Document):

    def on_update(self):

        # prevent loop
        if getattr(self, "ignore_on_update", False):
            return

        if not self.drawing_sync_tool_attachment:
            return

        files = []
        seen = set()

        for row in self.drawing_sync_tool_attachment:

            if row.pdf:
                name = row.pdf.strip()
                if name not in seen:
                    files.append({
                        "name": name,
                        "url": name   # store only filename
                    })
                    seen.add(name)

            if row.dxf:
                name = row.dxf.strip()
                if name not in seen:
                    files.append({
                        "name": name,
                        "url": name
                    })
                    seen.add(name)

        if files:
            map_local_revisions(files)


@frappe.whitelist()
def fetch_missing_drawings(docname):
    doc = frappe.get_doc("Drawing Sync Tool", docname)

    if not doc.url:
        frappe.throw("Please enter folder path")

    parsed = urlparse(doc.url)
    base_path = parsed.path

    if not os.path.exists(base_path):
        frappe.throw(f"Invalid path: {base_path}")

    files = os.listdir(base_path)

    existing_revisions = set(
        r.lower().strip()
        for r in frappe.db.get_all("Drawing Revision", pluck="drawing_revision")
    )

    doc.drawing_sync_tool_attachment = []

    for f in files:
        clean_name = f.strip()
        ext = clean_name.lower().split(".")[-1]

        if ext not in ["pdf", "dxf"]:
            continue

        matches = re.findall(r"\b\d+-\d+-\d+\b", clean_name)
        if not matches:
            continue

        revision = matches[0].lower().strip()

        if revision in existing_revisions:
            continue

        row = next(
            (r for r in doc.drawing_sync_tool_attachment
             if r.file_name and r.file_name.lower().strip() == revision),
            None
        )

        if not row:
            row = doc.append("drawing_sync_tool_attachment", {
                "file_name": revision
            })

        # ✅ STORE ONLY FILE NAME
        if ext == "pdf":
            row.pdf = clean_name
        else:
            row.dxf = clean_name

    doc.flags.ignore_on_update = True
    doc.save()

    return "Done"



from werkzeug.wrappers import Response

@frappe.whitelist(allow_guest=True)
def open_local_file(file_name):
    base_path = "/home/hrishikesh/Downloads"

    full_path = os.path.join(base_path, file_name)

    if not os.path.exists(full_path):
        frappe.throw(f"File not found: {file_name}")

    ext = file_name.split(".")[-1].lower()

    content_type_map = {
        "pdf": "application/pdf",
        "dxf": "application/dxf"
    }

    content_type = content_type_map.get(ext, "application/octet-stream")

    with open(full_path, "rb") as f:
        data = f.read()

    response = Response(data, content_type=content_type)
    response.headers["Content-Disposition"] = f'inline; filename="{file_name}"'

    return response



def map_local_revisions(files):

    if isinstance(files, str):
        files = frappe.parse_json(files)

    drawings_map = {}

    for f in files:
        file_name = f.get("name")
        file_url = f.get("url")   # this is just filename now

        if not file_name:
            continue

        matches = re.findall(r"\b\d+-\d+-\d+\b", file_name)
        if not matches:
            continue

        revision_name = matches[0]

        parts = revision_name.split("-")
        base_drawing = f"{parts[0]}-{parts[1]}"

        ext = file_name.split(".")[-1].lower().strip()

        if ext == "pdf":
            field = "file_url"
        elif ext == "dxf":
            field = "dxf_file_url"
        else:
            continue

        drawings_map.setdefault(base_drawing, {})
        drawings_map[base_drawing].setdefault(revision_name, {})
        drawings_map[base_drawing][revision_name][field] = file_url

    # APPLY TO DRAWING
    for base_drawing, revisions in drawings_map.items():

        drawing_name = frappe.db.get_value(
            "Drawing",
            {"name": ["like", f"{base_drawing}%"]},
            "name"
        )

        if not drawing_name:
            continue

        doc = frappe.get_doc("Drawing", drawing_name)

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

        # rename to latest revision
        latest_revision = max(
            revisions.keys(),
            key=lambda x: int(x.split("-")[-1])
        )

        if doc.name != latest_revision:
            if not frappe.db.exists("Drawing", latest_revision):
                if doc.name.startswith(base_drawing):
                    frappe.rename_doc("Drawing", doc.name, latest_revision)