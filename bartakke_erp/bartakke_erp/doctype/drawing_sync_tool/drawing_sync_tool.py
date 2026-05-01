# Copyright (c) 2026

import frappe
import os
import re
from urllib.parse import urlparse
from frappe.model.document import Document
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup


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
        frappe.throw("Please enter folder path or URL")

    source = doc.url.strip()

    # Detect URL properly
    is_url = source.startswith(("http://", "https://"))

    # Get existing revisions
    existing_revisions = set(
        r.lower().strip()
        for r in frappe.db.get_all("Drawing Revision", pluck="drawing_revision")
    )

    doc.drawing_sync_tool_attachment = []

    file_map = {}


    if not is_url:

        if not os.path.exists(source):
            frappe.throw(f"Path does not exist on server: {source}")

        try:
            files = os.listdir(source)
        except Exception as e:
            frappe.throw(f"Unable to read directory: {str(e)}")

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

            if revision not in file_map:
                file_map[revision] = {"pdf": None, "dxf": None}

            if ext == "pdf":
                file_map[revision]["pdf"] = clean_name
            else:
                file_map[revision]["dxf"] = clean_name

    else:
        try:
            response = requests.get(source, timeout=10)
        except Exception as e:
            frappe.throw(f"Failed to connect: {str(e)}")

        if response.status_code != 200:
            frappe.throw(f"Invalid URL or access denied ({response.status_code})")

        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.find_all("a"):
            href = link.get("href")

            if not href:
                continue

            file_name = href.split("/")[-1].strip()
            ext = file_name.lower().split(".")[-1]

            if ext not in ["pdf", "dxf"]:
                continue

            matches = re.findall(r"\b\d+-\d+-\d+\b", file_name)
            if not matches:
                continue

            revision = matches[0].lower().strip()

            if revision in existing_revisions:
                continue

            full_url = urljoin(source, href)

            if revision not in file_map:
                file_map[revision] = {"pdf": None, "dxf": None}

            if ext == "pdf":
                file_map[revision]["pdf"] = full_url
            else:
                file_map[revision]["dxf"] = full_url

    for revision, files in file_map.items():
        doc.append("drawing_sync_tool_attachment", {
            "file_name": revision,
            "pdf": files["pdf"],
            "dxf": files["dxf"]
        })

    doc.flags.ignore_on_update = True
    doc.save()

    return f"{len(file_map)} drawings synced"


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
