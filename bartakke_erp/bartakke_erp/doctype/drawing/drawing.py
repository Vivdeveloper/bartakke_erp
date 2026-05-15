# Copyright (c) 2026, Viv Choudhary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.utils import cint, cstr, now_datetime

def _norm_sheet_drawing(value):
    return cstr(value or "").strip()


def _replace_drawing_name_in_text(text, old, new):
    if not old or old == new:
        return text
    s = cstr(text)
    variants = [old, old.replace("/", "%2F")]
    if "/" in old:
        hy = old.replace("/", "-")
        if hy not in variants:
            variants.append(hy)
    for variant in variants:
        if variant in s:
            s = s.replace(variant, new)
    return s


DRAWING_REVISION_CHILD = "Drawing Revision"
DRAWING_REVISION_FIELD = "drawing_revision"
SORT_KEY_MISSING_REVISION = 1 << 30


class Drawing(Document):
    def autoname(self):
        computed = self._drawing_revision_id()
        if not cstr(self.sf_code).strip() or self.drawing_number in (None, ""):
            frappe.throw(
                _("SF Code and Drawing Number are required before naming the Drawing."),
                title=_("Drawing"),
            )
        self.name = computed

    def _drawing_revision_id(self):
        """Canonical id: {sf}-{drawing_number}-{revision} or .../{sheet} when sheet is set."""
        base = f"{self.sf_code}-{self.drawing_number}-{self.revision}"
        sheet = cstr(self.sheet).strip() if self.sheet else ""
        return f"{base}/{sheet}" if sheet else base

    @staticmethod
    def _revision_as_int(value):
        s = cstr(value).strip()
        return int(s) if s and s.isdigit() else None

    @staticmethod
    def _parse_revision_from_row_key(key, sf_code, drawing_number, sheet):
        key = cstr(key).strip()
        if not sf_code or drawing_number is None or drawing_number == "":
            return None
        prefix = f"{sf_code}-{drawing_number}-"
        if not key.startswith(prefix):
            return None
        if sheet:
            sheet = cstr(sheet).strip()
            slash_suffix, hyphen_suffix = f"/{sheet}", f"-{sheet}"
            if key.endswith(slash_suffix):
                mid = key[len(prefix) : -len(slash_suffix)]
            elif key.endswith(hyphen_suffix):
                mid = key[len(prefix) : -len(hyphen_suffix)]
            else:
                return None
        else:
            mid = key[len(prefix) :]
        return int(mid) if mid.isdigit() else None

    def _row_key_revision(self, key):
        return self._parse_revision_from_row_key(key, self.sf_code, self.drawing_number, self.sheet)

    def _max_row_revision_int(self):
        nums = [
            cint(r.get("revision"))
            for r in self.get(DRAWING_REVISION_FIELD) or []
            if r.get("revision") is not None
        ]
        return max(nums) if nums else None

    def _integration_hooks_skipped(self):
        return bool(frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_patch)

    def _coerce_revision_int_for_row(self, row_key_str):
        n = self._revision_as_int(self.revision)
        return self._row_key_revision(row_key_str) if n is None else n

    def _has_drawing_revision_row(self, drawing_revision_key):
        key = cstr(drawing_revision_key).strip()
        if not key:
            return False
        return any(
            cstr(r.get("drawing_revision") or "").strip() == key
            for r in self.get(DRAWING_REVISION_FIELD) or []
        )

    @staticmethod
    def _drawing_revision_row_score(row):
        score = 0
        if row.get("file_url"):
            score += 2
        if row.get("dxf_file_url"):
            score += 2
        if row.get("revision_time"):
            score += 1
        if row.get("revision") is not None:
            score += 1
        return score

    def _dedupe_drawing_revision_rows(self):
        by_key = {}
        for row in list(self.get(DRAWING_REVISION_FIELD) or []):
            key = cstr(row.get("drawing_revision") or "").strip()
            if not key:
                continue
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = row
                continue
            if self._drawing_revision_row_score(row) > self._drawing_revision_row_score(existing):
                self.remove(existing)
                by_key[key] = row
            else:
                self.remove(row)

    def _prune_blank_drawing_revision_rows_when_canonical_exists(self):
        canonical = cstr(self._drawing_revision_id()).strip()
        if not canonical or not self._has_drawing_revision_row(canonical):
            return
        for row in list(self.get(DRAWING_REVISION_FIELD) or []):
            if cstr(row.get("drawing_revision") or "").strip():
                continue
            if row.get("file_url") or row.get("dxf_file_url"):
                continue
            self.remove(row)

    def _append_drawing_revision_row(self, drawing_revision_key, revision_int):
        if self._has_drawing_revision_row(drawing_revision_key):
            return
        self.append(
            DRAWING_REVISION_FIELD,
            {
                "drawing_revision": drawing_revision_key,
                "revision": revision_int,
                "revision_time": now_datetime(),
                "created_by": frappe.session.user,
            },
        )

    def _fill_child_revision_from_key_if_missing(self):
        for row in self.get(DRAWING_REVISION_FIELD) or []:
            if row.get("revision") is None:
                n = self._row_key_revision(row.get("drawing_revision"))
                if n is not None:
                    row.revision = n

    def _sync_parent_revision_from_children(self):
        m = self._max_row_revision_int()
        if m is not None:
            self.revision = cstr(m)

    def _validate_contiguous_row_revisions(self):
        if self._integration_hooks_skipped():
            return

        rows = self.get(DRAWING_REVISION_FIELD) or []
        if not rows:
            return

        values = []
        for row in rows:
            if row.get("revision") is None:
                frappe.throw(
                    _("Set Revision on each row (or set Drawing Revision id so it can be filled)."),
                    title=_("Drawing Revision"),
                )
            n = cint(row.get("revision"))
            if n < 0:
                frappe.throw(_("Revision must be zero or positive."), title=_("Drawing Revision"))
            values.append(n)

        if cint(self.manual_revision):
            return

        mx = max(values)
        expected, actual = set(range(0, mx + 1)), set(values)
        if actual != expected:
            missing = ", ".join(str(x) for x in sorted(expected - actual))
            frappe.throw(
                _(
                    "Revision numbers must run in order from 0 with no skips. "
                    "Add the missing revision(s) before higher numbers: {0}."
                ).format(missing),
                title=_("Drawing Revision"),
            )

    def _validate_parent_revision_digits(self):
        s = cstr(self.revision).strip()
        if s and not s.isdigit():
            frappe.throw(
                _("Revision must be a non-negative whole number (0, 1, 2, …)."),
                title=_("Revision"),
            )

    def _drawing_revision_sort_key(self, row):
        if row.get("revision") is not None:
            primary = cint(row.get("revision"))
        else:
            primary = self._row_key_revision(row.get("drawing_revision"))
            if primary is None:
                primary = SORT_KEY_MISSING_REVISION
        return (primary, cstr(row.get("drawing_revision") or ""))

    def _sort_drawing_revision_rows(self):
        rows = self.get(DRAWING_REVISION_FIELD)
        if not rows:
            return
        rows.sort(key=self._drawing_revision_sort_key)
        for i, row in enumerate(rows, start=1):
            row.idx = i

    def _normalize_child_drawing_revision_slash_keys(self):
        sheet = cstr(self.sheet).strip() if self.sheet else ""
        if not sheet:
            return
        hyphen_suffix, slash_suffix = f"-{sheet}", f"/{sheet}"
        for row in self.get(DRAWING_REVISION_FIELD) or []:
            k = (row.get("drawing_revision") or "").strip()
            if k.endswith(hyphen_suffix):
                row.drawing_revision = k[: -len(hyphen_suffix)] + slash_suffix

    def _append_row_if_parent_revision_changed(self, prev):
        if prev is None or cstr(prev.revision) == cstr(self.revision):
            return
        new_id = self._drawing_revision_id()
        if self._has_drawing_revision_row(new_id):
            return
        self._append_drawing_revision_row(new_id, self._coerce_revision_int_for_row(new_id))

    def _ensure_default_revision_rows(self):
        rows = self.get(DRAWING_REVISION_FIELD) or []
        rid = self._drawing_revision_id()
        rev_int = self._coerce_revision_int_for_row(rid)

        if self._has_drawing_revision_row(rid):
            return

        if not rows:
            self._append_drawing_revision_row(rid, rev_int)
            return

        blank_rows = [r for r in rows if not cstr(r.get("drawing_revision") or "").strip()]
        if len(blank_rows) == 1:
            row = blank_rows[0]
            row.drawing_revision = rid
            row.revision = rev_int
            row.revision_time = now_datetime()
            row.created_by = frappe.session.user

    def _stamp_canonical_revision_metadata(self):
        canonical = {self.name, self._drawing_revision_id()}
        for row in self.get(DRAWING_REVISION_FIELD) or []:
            if (row.get("drawing_revision") or "").strip() not in canonical:
                continue
            if not row.revision_time:
                row.revision_time = now_datetime()
            if not row.created_by:
                row.created_by = frappe.session.user

    def before_validate(self):
        if not self.name:
            return

        self._normalize_child_drawing_revision_slash_keys()
        self._append_row_if_parent_revision_changed(self.get_doc_before_save())
        self._ensure_default_revision_rows()
        self._dedupe_drawing_revision_rows()
        self._prune_blank_drawing_revision_rows_when_canonical_exists()
        self._fill_child_revision_from_key_if_missing()
        self._sort_drawing_revision_rows()
        self._validate_contiguous_row_revisions()
        self._sync_parent_revision_from_children()
        self._validate_parent_revision_digits()
        self._stamp_canonical_revision_metadata()

    def _validate_duplicate_sf_drawing_number_sheet(self):
        """One Drawing per (sf_code, drawing_number, sheet); sheet blank matches blank only."""
        if self._integration_hooks_skipped():
            return
        sf = cstr(self.sf_code or "").strip()
        dn = cstr(self.drawing_number or "").strip()
        if not sf or not dn:
            return
        sh = _norm_sheet_drawing(self.sheet)

        filters = {"sf_code": sf, "drawing_number": dn}
        if self.name:
            filters["name"] = ["!=", self.name]

        for row in frappe.get_all(
            "Drawing",
            filters=filters,
            fields=["name", "item_code", "sheet"],
        ):
            if _norm_sheet_drawing(row.get("sheet")) != sh:
                continue
            frappe.throw(
                _(
                    "Duplicate Drawing: SF Code {0}, Drawing Number {1}, and Sheet {2} already exist on {3} "
                    "(Item Code {4})."
                ).format(
                    frappe.bold(sf),
                    frappe.bold(dn),
                    frappe.bold(sh or _("(blank)")),
                    frappe.bold(row.name),
                    frappe.bold(cstr(row.get("item_code") or "").strip() or _("(not set)")),
                ),
                title=_("Duplicate Drawing"),
            )

    def validate(self):
        self._validate_duplicate_sf_drawing_number_sheet()

    def _push_revision_to_item(self):
        """Keep Item.custom_revision and Item.custom_sheet in sync with this Drawing."""
        if not self.item_code:
            return
        rev = cstr(self.revision or "")
        sheet = _norm_sheet_drawing(self.sheet)

        row = frappe.db.get_value(
            "Item",
            self.item_code,
            ["custom_revision", "custom_sheet"],
            as_dict=True,
        )
        if not row:
            return

        updates = {}
        if cstr(row.get("custom_revision") or "") != rev:
            updates["custom_revision"] = rev
        if _norm_sheet_drawing(row.get("custom_sheet")) != sheet:
            updates["custom_sheet"] = sheet

        if updates:
            frappe.db.set_value("Item", self.item_code, updates)

    def before_save(self):
        if self._integration_hooks_skipped():
            return

        if not self.is_new():
            new_name = self._drawing_revision_id()
            if new_name and new_name != self.name:
                if frappe.db.exists(self.doctype, new_name):
                    frappe.throw(
                        _("Cannot rename to {0}: another Drawing already has this name.").format(
                            frappe.bold(new_name)
                        ),
                        title=_("Drawing"),
                    )

                self.name = rename_doc(
                    doc=self,
                    new=new_name,
                    merge=False,
                    force=False,
                    validate=True,
                    show_alert=False,
                    rebuild_search=False,
                )
                for row in self.get(DRAWING_REVISION_FIELD) or []:
                    row.parent = self.name

        self._push_revision_to_item()

    def after_rename(self, old, new, merge):
        if merge or self._integration_hooks_skipped():
            return

        rows = frappe.get_all(
            DRAWING_REVISION_CHILD,
            filters={
                "parent": new,
                "parenttype": self.doctype,
                "parentfield": DRAWING_REVISION_FIELD,
            },
            fields=["name", "drawing_revision", "file_url", "dxf_file_url"],
        )
        old_variants = (old, old.replace("/", "%2F"))
        if "/" in old:
            old_variants = old_variants + (old.replace("/", "-"),)
        for row in rows:
            updates = {}
            dr = (row.get("drawing_revision") or "").strip()
            if dr in old_variants:
                updates["drawing_revision"] = new
            for fname in ("file_url", "dxf_file_url"):
                val = row.get(fname)
                if not val:
                    continue
                replaced = _replace_drawing_name_in_text(val, old, new)
                if replaced != cstr(val):
                    updates[fname] = replaced
            if updates:
                frappe.db.set_value(DRAWING_REVISION_CHILD, row.name, updates, update_modified=False)
