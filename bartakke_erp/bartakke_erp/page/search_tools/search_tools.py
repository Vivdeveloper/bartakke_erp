# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

"""Search Tools page: 'Search for Revision' — search Items by Drawing No. or
Description and bulk-edit Revision / Development Size A & B / Thickness.

Saves go through the full Item controller (doc.save()) — NOT a raw db update —
because these fields carry real side effects on this doctype:
  - custom_t (Thickness) participates in Item autoname/rename for dimensional
    item groups (see bartakke_erp.bartakke_erp.api.item.rename_item).
  - custom_revision drives the linked Drawing's revision history and naming,
    normally synced by a client-side after_save call to api.item.get_revision.
    A server-side doc.save() alone does not trigger that, so we call it here
    explicitly to keep the Drawing in sync.
"""

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt

from bartakke_erp.bartakke_erp.api.item import get_revision as sync_drawing_revision

EDITABLE_FIELDS = (
	"custom_revision",
	"custom_development_size_a",
	"custom_development_size_b",
	"custom_t",
)

# Fields that drive the Area/Weight formula below — mirrors the "Weight and Area
# Calculation" Client Script on Item (fixtures/client_script.json). That script
# only runs in the browser against a bound `frm`, so edits made through this
# page's plain <input> grid never trigger it; replicate it here so Area/Weight
# stay in sync when Development Size/Thickness are bulk-edited via this tool.
DIMENSION_FIELDS = ("custom_development_size_a", "custom_development_size_b", "custom_t")


def _recalc_area_weight(doc):
	size_a = flt(doc.custom_development_size_a)
	size_b = flt(doc.custom_development_size_b)
	thickness = flt(doc.custom_t)
	density = flt(doc.custom_density)

	if size_a and size_b:
		doc.custom_area = (size_a * size_b) / 1000000

	if size_a and size_b and thickness and density:
		doc.weight_per_unit = (size_a * size_b * thickness * density) / 1000000


SEARCH_FIELDS = [
	"name as item_code",
	"item_name",
	"description",
	"custom_material",
	"custom_sf_code",
	"custom_drawing_no",
	"custom_revision",
	"custom_development_size_a",
	"custom_development_size_b",
	"custom_t",
]


@frappe.whitelist()
def search_items_for_revision(drawing_no=None, description=None):
	drawing_no = cstr(drawing_no).strip()
	description = cstr(description).strip()

	if not drawing_no and not description:
		return []

	filters = {"disabled": 0}
	if drawing_no:
		filters["custom_drawing_no"] = drawing_no

	or_filters = None
	if description:
		or_filters = [
			["item_name", "like", f"%{description}%"],
			["description", "like", f"%{description}%"],
		]

	return frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=SEARCH_FIELDS,
		order_by="item_name",
		limit_page_length=200,
	)


@frappe.whitelist()
def save_revision_changes(rows):
	rows = frappe.parse_json(rows)
	if not rows:
		frappe.throw(_("No changes to save."))

	saved, errors = [], []

	for row in rows:
		item_code = row.get("item_code")
		if not item_code:
			continue

		try:
			doc = frappe.get_doc("Item", item_code)
			changed = False
			dims_changed = False
			for field in EDITABLE_FIELDS:
				if field in row and cstr(row.get(field)) != cstr(doc.get(field)):
					doc.set(field, row.get(field))
					changed = True
					if field in DIMENSION_FIELDS:
						dims_changed = True

			if not changed:
				continue

			if dims_changed:
				_recalc_area_weight(doc)

			doc.save()

			# Replicate the Item form's after_save call so the linked Drawing's
			# revision history/name stays in sync with custom_revision.
			sync_drawing_revision(json.dumps({"item_code": doc.name, "custom_revision": doc.custom_revision}))
			doc.reload()
			# Committed per-row: a later row's failure must roll back only its own
			# partial writes, not already-saved rows earlier in this batch.
			frappe.db.commit()

			saved.append(
				{
					"old_item_code": item_code,
					"item_code": doc.name,
					"custom_revision": doc.custom_revision,
					"custom_development_size_a": doc.custom_development_size_a,
					"custom_development_size_b": doc.custom_development_size_b,
					"custom_t": doc.custom_t,
				}
			)
		except Exception as e:
			frappe.db.rollback()
			errors.append({"item_code": item_code, "error": str(e)})

	return {"saved": saved, "errors": errors}
