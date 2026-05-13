# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

"""Page API: PDF and DXF File Settings + JSON list of scanned files; move to local target folder."""

from __future__ import annotations

import json
import os
import re
import shutil
from urllib.parse import unquote, urlparse, urljoin

import frappe
import requests
from bs4 import BeautifulSoup
from frappe import _

SETTINGS = "PDF and DXF File Settings"
ITEMS_JSON = "pdf_and_dxf_file_page_items.json"
LEGACY_JSON = "pdf_and_dxf_file_page_state.json"


def _items_file():
	return frappe.get_site_path("private", "files", ITEMS_JSON)


def _settings():
	if frappe.db.exists(SETTINGS, SETTINGS):
		return frappe.get_doc(SETTINGS, SETTINGS)
	d = frappe.new_doc(SETTINGS)
	d.insert(ignore_permissions=True)
	return d


def _read_items() -> list:
	path = _items_file()
	try:
		os.makedirs(os.path.dirname(path), exist_ok=True)
	except OSError:
		pass
	if os.path.isfile(path):
		try:
			with open(path, encoding="utf-8") as f:
				return list(json.load(f).get("pdf_and_dxf_file_items") or [])
		except (json.JSONDecodeError, OSError):
			return []
	legacy = frappe.get_site_path("private", "files", LEGACY_JSON)
	if os.path.isfile(legacy):
		try:
			with open(legacy, encoding="utf-8") as f:
				old = list(json.load(f).get("pdf_and_dxf_file_items") or [])
			if old:
				_write_items(old)
			return old
		except (json.JSONDecodeError, OSError):
			pass
	return []


def _write_items(items: list) -> None:
	path = _items_file()
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump({"pdf_and_dxf_file_items": items}, f, indent=2, default=str)


def _stem(name: str) -> str:
	n = (name or "").strip()
	return n.rsplit(".", 1)[0] if "." in n else n


def _triple_key(stem: str) -> str:
	"""Leading sf-drawing-rev (digits only per segment) so '11-17384-1 copy' matches '11-17384-1'."""
	s = (stem or "").strip()
	m = re.match(r"^(\d+-\d+-\d+)", s)
	return m.group(1) if m else s
def _item_code_for_stem(stem: str) -> str:
	parts = [p.strip() for p in (stem or "").split("-") if p.strip()]
	if len(parts) < 2:
		return ""
	sf, drw, rev = parts[0], parts[1], parts[2] if len(parts) > 2 else None
	drawings = [drw]
	if len(drw) > 1 and drw.startswith("1") and drw[1:].isdigit():
		drawings.append(drw[1:])
	for d in dict.fromkeys(drawings):
		filters = {"custom_sf_code": sf, "custom_drawing_no": d, "disabled": 0}
		if rev:
			code = frappe.db.get_value("Item", {**filters, "custom_revision": rev}, "item_code")
			if code:
				return code
		rows = frappe.get_all(
			"Item",
			filters=filters,
			fields=["item_code"],
			order_by="modified desc",
			limit_page_length=1,
		)
		if rows and rows[0].get("item_code"):
			return rows[0]["item_code"]
	return ""


def _with_item_codes(rows: list[dict]) -> list[dict]:
	cache: dict[str, str] = {}
	out = []
	for row in rows:
		r = dict(row)
		st = _stem(r.get("file_name") or "")
		key = _triple_key(st)
		if key not in cache:
			cache[key] = _item_code_for_stem(key)
		r["item_code"] = cache[key]
		out.append(r)
	return out


def _state():
	doc = _settings()
	src = (doc.source_url or "").strip()
	tgt = (doc.target_url or "").strip()
	raw = _read_items() if src else []
	return {"source_url": src, "target_url": tgt, "pdf_and_dxf_file_items": _with_item_codes(raw) if raw else []}


def _norm_path(val: str) -> str:
	val = (val or "").strip()
	p = urlparse(val)
	if p.scheme != "file":
		return val
	path = unquote(p.path or "")
	if len(path) >= 3 and path[0] == "/" and path[2] == ":" and path[1].isalpha():
		path = path[1:]
	return path.rstrip("/") or path


def _row_dict(file_name: str, ext: str, source_path: str, target_path: str) -> dict:
	return {"file_name": file_name, "extension": ext, "source_path": source_path, "target_path": target_path, "moved": False}


def _scan(source_raw: str, target_raw: str) -> list[dict]:
	items: list[dict] = []
	is_http = urlparse(source_raw).scheme in ("http", "https")
	tb = (target_raw or "").strip()
	ttp = urlparse(tb)
	if tb and ttp.scheme in ("http", "https"):
		http_base, local_dir = tb.rstrip("/"), ""
	else:
		http_base, local_dir = "", _norm_path(tb) if tb else ""

	def tgt_for(fname: str) -> str:
		if http_base:
			return urljoin(http_base + "/", fname)
		if local_dir:
			return os.path.join(local_dir, fname)
		return ""

	if not is_http:
		root = _norm_path(source_raw)
		if not os.path.isdir(root):
			frappe.throw(_("Source must be a folder path on the server: {0}").format(root))
		try:
			names = sorted(os.listdir(root))
		except OSError as e:
			frappe.throw(_("Cannot read folder: {0}").format(str(e)))
		for name in names:
			name = name.strip()
			if "." not in name:
				continue
			ext = name.rsplit(".", 1)[-1].lower()
			if ext not in ("pdf", "dxf"):
				continue
			full = os.path.join(root, name)
			if os.path.isfile(full):
				items.append(_row_dict(name, ext, full, tgt_for(name)))
	else:
		try:
			resp = requests.get(source_raw, timeout=20)
		except Exception as e:
			frappe.throw(_("Could not open Source URL: {0}").format(str(e)))
		if resp.status_code != 200:
			frappe.throw(_("Source URL returned HTTP {0}").format(resp.status_code))
		for link in BeautifulSoup(resp.text, "html.parser").find_all("a"):
			href = link.get("href")
			if not href:
				continue
			file_name = href.split("/")[-1].strip()
			if "." not in file_name:
				continue
			ext = file_name.rsplit(".", 1)[-1].lower()
			if ext not in ("pdf", "dxf"):
				continue
			items.append(_row_dict(file_name, ext, urljoin(source_raw, href), tgt_for(file_name)))
	return items


def _move_to(items: list, target_dir: str) -> tuple[int, int]:
	moved = skipped = 0
	os.makedirs(target_dir, exist_ok=True)
	for row in items:
		if row.get("moved"):
			continue
		src = row.get("source_path") or ""
		if urlparse(src).scheme in ("http", "https"):
			frappe.throw(_("Cannot move files listed from HTTP. Use a local source folder."))
		src_path = _norm_path(src)
		if not os.path.isfile(src_path):
			continue
		name = row.get("file_name") or os.path.basename(src_path)
		dest = os.path.join(target_dir, name)
		if os.path.exists(dest):
			try:
				if os.path.samefile(src_path, dest):
					row["moved"] = True
					row["target_path"] = dest
					moved += 1
					continue
			except OSError:
				pass
			skipped += 1
			continue
		shutil.move(src_path, dest)
		row["moved"] = True
		row["target_path"] = dest
		moved += 1
	return moved, skipped


def _move_msg(moved: int, skipped: int) -> str:
	if moved and skipped:
		return _("Moved {0} file(s); skipped {1} (already in target)").format(moved, skipped)
	if moved:
		return _("Moved {0} file(s)").format(moved)
	if skipped:
		return _("Skipped {0} file(s) (already in target)").format(skipped)
	return _("Nothing to move")


@frappe.whitelist()
def get_page_state():
	return _state()


@frappe.whitelist()
def save_page_urls(source_url=None, target_url=None):
	doc = _settings()
	if source_url is not None:
		doc.source_url = (source_url or "").strip()
		if not doc.source_url:
			_write_items([])
	if target_url is not None:
		doc.target_url = (target_url or "").strip()
	doc.save()
	return _state()


@frappe.whitelist()
def auto_search_files():
	st = _state()
	if not st["source_url"].strip():
		frappe.throw(_("Set Source URL (PDF and DXF File Settings)."))
	items = _scan(st["source_url"], st["target_url"])
	_write_items(items)
	return {"message": _("Found {0} file(s)").format(len(items)), **_state()}


@frappe.whitelist()
def move_files_to_target():
	st = _state()
	if not st["source_url"].strip():
		frappe.throw(_("Set Source URL first."))
	items = _read_items()
	if not items:
		frappe.throw(_("Run Auto Search first."))
	tgt = (st.get("target_url") or "").strip()
	if not tgt:
		frappe.throw(_("Set Target URL (local folder on the server)."))
	if urlparse(tgt).scheme in ("http", "https"):
		frappe.throw(_("Target must be a local folder path."))
	moved, skipped = _move_to(items, _norm_path(tgt))
	_write_items([] if moved > 0 else items)
	return {"message": _move_msg(moved, skipped), **_state()}
