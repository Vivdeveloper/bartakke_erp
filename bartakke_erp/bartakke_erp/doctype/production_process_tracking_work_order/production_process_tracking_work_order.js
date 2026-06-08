// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Process Tracking Work Order", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.production_plan) {
			return;
		}
		frappe.call({
			method:
				"bartakke_erp.bartakke_erp.doctype.production_process_tracking_work_order.production_process_tracking_work_order.get_linked_ppt",
			args: { production_plan: frm.doc.production_plan },
			callback(r) {
				if (!r.message) {
					return;
				}
				frm.add_custom_button(__("Open Lot Tracking"), () => {
					frappe.set_route("Form", "Production Process Tracking", r.message);
				});
			},
		});
	},
	production_process_tracking_template(frm) {
		sync_stages_from_template(frm);
	},
});

frappe.ui.form.on("Production Process Tracking Work Order Stage", {
	completed(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.completed) {
			frappe.model.set_value(cdt, cdn, "completed_by", frappe.session.user);
			frappe.model.set_value(cdt, cdn, "completed_on", frappe.datetime.now_datetime());
			return;
		}
		frappe.model.set_value(cdt, cdn, "completed_by", "");
		frappe.model.set_value(cdt, cdn, "completed_on", "");
	},
});

function sync_stages_from_template(frm) {
	const template = frm.doc.production_process_tracking_template;
	if (!template) {
		frm.clear_table("production_process_tracking_work_order_stages");
		frm.refresh_field("production_process_tracking_work_order_stages");
		return;
	}

	frappe.model.with_doc("Production Process Tracking Template", template, () => {
		const template_doc = frappe.get_doc(
			"Production Process Tracking Template",
			template
		);
		const rows = (template_doc.production_process_tracking_template_items || [])
			.slice()
			.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));

		frm.clear_table("production_process_tracking_work_order_stages");
		rows.forEach((row) => {
			if (!row.production_stages) {
				return;
			}
			frm.add_child("production_process_tracking_work_order_stages", {
				production_stage: row.production_stages,
			});
		});
		frm.refresh_field("production_process_tracking_work_order_stages");
	});
}
