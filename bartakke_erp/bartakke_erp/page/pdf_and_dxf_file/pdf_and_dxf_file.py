# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

"""Desk page API: URLs from Settings; scan JSON; move clears scan list after files moved; Item code from stem."""

from __future__ import annotations

import json
import os
import shutil
from urllib.parse import unquote, urlparse, urljoin

import frappe
import requests
from bs4 import BeautifulSoup
from frappe import _

SETTINGS_DOCTYPE = "PDF and DXF File Settings"
_ITEMS_FILENAME = "pdf_and_dxf_file_page_items.json"
_LEGACY_STATE_FILENAME = "pdf_and_dxf_file_page_state.json"


def _items_path() -> str:
	return frappe.get_site_path("private", "files", _ITEMS_FILENAME)


def _legacy_state_path() -> str:
	return frappe.get_site_path("private", "files", _LEGACY_STATE_FILENAME)


def _get_settings_doc():
	"""Single DocType row; create if missing (first run)."""
	name = SETTINGS_DOCTYPE
	if frappe.db.exists(SETTINGS_DOCTYPE, name):
		return frappe.get_doc(SETTINGS_DOCTYPE, name)
	doc = frappe.new_doc(SETTINGS_DOCTYPE)
	doc.insert(ignore_permissions=True)
	return doc


def _load_items_only() -> list:
	path = _items_path()
	try:
		os.makedirs(os.path.dirname(path), exist_ok=True)
	except OSError:
		pass
	if os.path.isfile(path):
		try:
			with open(path, encoding="utf-8") as f:
				data = json.load(f)
			return list(data.get("pdf_and_dxf_file_items") or [])
		except (json.JSONDecodeError, OSError):
			return []

	legacy = _legacy_state_path()
	if os.path.isfile(legacy):
		try:
			with open(legacy, encoding="utf-8") as f:
				data = json.load(f)
			items = list(data.get("pdf_and_dxf_file_items") or [])
			if items:
				_save_items_only(items)
			return items
		except (json.JSONDecodeError, OSError):
			pass
	return []


def _save_items_only(items: list) -> None:
	path = _items_path()
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump({"pdf_and_dxf_file_items": items}, f, indent=2, default=str)


def _file_stem_from_name(filename: str) -> str:
	fn = (filename or "").strip()
	if "." in fn:
		return fn.rsplit(".", 1)[0]
	return fn


def _drawing_no_candidates(drw: str) -> list[str]:
	"""Try exact drawing no from filename, then without a leading 1 (e.g. 17384 vs 7384 on Item)."""
	drw = (drw or "").strip()
	if not drw:
		return []
	out = [drw]
	if len(drw) > 1 and drw.startswith("1") and drw[1:].isdigit():
		out.append(drw[1:])
	return list(dict.fromkeys(out))


def _lookup_item_code(sf: str, drw: str, rev: str | None) -> str:
	"""Resolve Item.item_code from custom_sf_code, custom_drawing_no, optional custom_revision."""
	for d in _drawing_no_candidates(drw):
		base = {"custom_sf_code": sf, "custom_drawing_no": d, "disabled": 0}
		if rev is not None:
			code = frappe.db.get_value("Item", {**base, "custom_revision": rev}, "item_code")
			if code:
				return code
		rows = frappe.get_all(
			"Item",
			filters=base,
			fields=["item_code"],
			order_by="modified desc",
			limit_page_length=1,
		)
		if rows:
			return rows[0].get("item_code") or ""
	return ""


def _lookup_item_code_from_stem(stem: str) -> str:
	stem = (stem or "").strip()
	if not stem:
		return ""
	parts = [p.strip() for p in stem.split("-") if p.strip()]
	if len(parts) < 2:
		return ""
	sf, drw = parts[0], parts[1]
	rev = parts[2] if len(parts) >= 3 else None
	return _lookup_item_code(sf, drw, rev)


def _enrich_items_with_item_code(items: list[dict]) -> list[dict]:
	"""Attach item_code per file row from Item (custom_sf_code / custom_drawing_no / custom_revision)."""
	cache: dict[str, str] = {}
	out: list[dict] = []
	for row in items:
		r = dict(row)
		stem = _file_stem_from_name(r.get("file_name") or "")
		if stem not in cache:
			cache[stem] = _lookup_item_code_from_stem(stem)
		r["item_code"] = cache[stem]
		out.append(r)
	return out


def _load_state() -> dict:
	doc = _get_settings_doc()
	src = (doc.source_url or "").strip()
	tgt = (doc.target_url or "").strip()
	# Without a configured source, do not surface stale rows (URLs live in Settings; JSON can lag).
	items_raw = _load_items_only() if src else []
	items = _enrich_items_with_item_code(items_raw) if items_raw else []
	return {
		"source_url": src,
		"target_url": tgt,
		"pdf_and_dxf_file_items": items,
	}


def _normalize_fs_path(value: str) -> str:
	value = (value or "").strip()
	parsed = urlparse(value)
	if parsed.scheme != "file":
		return value
	path = unquote(parsed.path or "")
	if len(path) >= 3 and path[0] == "/" and path[2] == ":" and path[1].isalpha():
		path = path[1:]
	return path.rstrip("/") or path


def _scan_pdf_dxf_items(source_raw: str, target_raw: str) -> list[dict]:
	"""Build rows for every PDF/DXF under Source (local dir or http listing)."""
	items: list[dict] = []
	parsed = urlparse(source_raw)
	is_http = parsed.scheme in ("http", "https")
	target_base = (target_raw or "").strip()
	target_tp = urlparse(target_base)
	if target_base and target_tp.scheme in ("http", "https"):
		target_http_base = target_base.rstrip("/")
		target_local_dir = ""
	else:
		target_http_base = ""
		target_local_dir = _normalize_fs_path(target_base) if target_base else ""

	if not is_http:
		root = _normalize_fs_path(source_raw)
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
			src_full = os.path.join(root, name)
			if not os.path.isfile(src_full):
				continue
			if target_http_base:
				tgt = urljoin(target_http_base + "/", name)
			elif target_local_dir:
				tgt = os.path.join(target_local_dir, name)
			else:
				tgt = ""
			items.append(
				{
					"file_name": name,
					"extension": ext,
					"source_path": src_full,
					"target_path": tgt,
					"moved": False,
				}
			)
	else:
		try:
			resp = requests.get(source_raw, timeout=20)
		except Exception as e:
			frappe.throw(_("Could not open Source URL: {0}").format(str(e)))
		if resp.status_code != 200:
			frappe.throw(_("Source URL returned HTTP {0}").format(resp.status_code))

		soup = BeautifulSoup(resp.text, "html.parser")
		for link in soup.find_all("a"):
			href = link.get("href")
			if not href:
				continue
			file_name = href.split("/")[-1].strip()
			if "." not in file_name:
				continue
			ext = file_name.rsplit(".", 1)[-1].lower()
			if ext not in ("pdf", "dxf"):
				continue
			src_full = urljoin(source_raw, href)
			if target_http_base:
				tgt = urljoin(target_http_base + "/", file_name)
			elif target_local_dir:
				tgt = os.path.join(target_local_dir, file_name)
			else:
				tgt = ""
			items.append(
				{
					"file_name": file_name,
					"extension": ext,
					"source_path": src_full,
					"target_path": tgt,
					"moved": False,
				}
			)

	return items


def _move_scanned_rows_to_folder(items: list, target_dir: str) -> tuple[int, int]:
	"""Move local files that are not yet moved. Skips if target already exists (no overwrite). Returns (moved, skipped_duplicate)."""
	moved = 0
	skipped_dup = 0
	os.makedirs(target_dir, exist_ok=True)
	for row in items:
		if row.get("moved"):
			continue
		src = row.get("source_path") or ""
		if urlparse(src).scheme in ("http", "https"):
			frappe.throw(_("Cannot move files that were listed from HTTP. Use a local Source folder."))
		src_path = _normalize_fs_path(src)
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
			skipped_dup += 1
			continue
		shutil.move(src_path, dest)
		row["moved"] = True
		row["target_path"] = dest
		moved += 1
	return moved, skipped_dup


@frappe.whitelist()
def get_page_state():
	return _load_state()


@frappe.whitelist()
def save_page_urls(source_url=None, target_url=None):
	doc = _get_settings_doc()
	if source_url is not None:
		doc.source_url = (source_url or "").strip()
		if not doc.source_url:
			_save_items_only([])
	if target_url is not None:
		doc.target_url = (target_url or "").strip()
	doc.save()
	return _load_state()


@frappe.whitelist()
def auto_search_files():
	st = _load_state()
	src = st["source_url"].strip()
	if not src:
		frappe.throw(_("Enter Source URL in PDF and DXF File Settings or on this page, then save."))
	tgt = st["target_url"].strip()
	items = _scan_pdf_dxf_items(src, tgt)
	_save_items_only(items)
	return {"message": _("Found {0} file(s)").format(len(items)), **_load_state()}


@frappe.whitelist()
def move_files_to_target():
	st = _load_state()
	if not st["source_url"].strip():
		frappe.throw(_("Set Source URL first (PDF and DXF File Settings or Save URLs)."))
	items = _load_items_only()
	if not items:
		frappe.throw(_("No scanned files. Run Auto Search first."))
	tgt = st.get("target_url", "").strip()
	if not tgt:
		frappe.throw(_("Enter Target URL (local folder path to move into)"))

	if urlparse(tgt).scheme in ("http", "https"):
		frappe.throw(_("Move only supports a local Target URL / folder path on the server"))

	target_dir = _normalize_fs_path(tgt)
	moved, skipped_dup = _move_scanned_rows_to_folder(items, target_dir)
	if moved > 0:
		# Reset scan table only; keep Source/Target URLs in Settings for the next Auto Search.
		_save_items_only([])
	else:
		_save_items_only(items)
	if moved and skipped_dup:
		msg = _("Moved {0} file(s); skipped {1} (already in target)").format(moved, skipped_dup)
	elif moved:
		msg = _("Moved {0} file(s)").format(moved)
	elif skipped_dup:
		msg = _("Skipped {0} file(s) (already in target)").format(skipped_dup)
	else:
		msg = _("Nothing to move")
	return {"message": msg, **_load_state()}
