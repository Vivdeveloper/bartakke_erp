// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

// Server-side rename (e.g. before_save rename_doc) returns the doc under a new `name`.
// frappe.model.sync then add_to_locals under the new key while frm.docname stays old,
// so refresh() loads the wrong row and /app/drawing/<name> does not update.
(function () {
	if (frappe.model._bartakke_drawing_sync_after_rename) {
		return;
	}
	frappe.model._bartakke_drawing_sync_after_rename = true;
	const orig_sync = frappe.model.sync;
	frappe.model.sync = function (r) {
		const ret = orig_sync.apply(this, arguments);
		const frm = cur_frm;
		if (!frm || frm.doctype !== "Drawing" || !r?.docs?.length) {
			return ret;
		}
		const d = r.docs.find((doc) => doc.doctype === "Drawing");
		if (!d?.name || !frm.docname || d.name === frm.docname) {
			return ret;
		}
		const old = frm.docname;
		frm.docname = d.name;
		if (locals[frm.doctype]?.[old]) {
			delete locals[frm.doctype][old];
		}
		return ret;
	};
})();

frappe.ui.form.on("Drawing", {
	after_save(frm) {
		const route = frappe.get_route();
		if (route[0] !== "Form") {
			return;
		}
		const layout = frappe.router.doctype_layout || frm.doctype;
		if (route[1] !== layout && route[1] !== frm.doctype) {
			return;
		}
		const route_name = route.length > 2 ? route.slice(2).join("/") : "";
		if (!route_name || route_name === frm.docname) {
			return;
		}
		frappe.route_flags.replace_route = true;
		frappe.set_route("Form", layout, frm.docname);
	},
});
