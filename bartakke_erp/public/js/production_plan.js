frappe.ui.form.on("Production Plan", {

	refresh(frm) {

		if (frm.doc.docstatus === 1) {

			frm.add_custom_button(__('Sales Order'), () => {
				frm.trigger('make_so');
			}, __('Create'));

			frm.add_custom_button(__('Lot Generation'), () => {
				frm.trigger('make_production_process_tracking');
			}, __('Create'));
		}

		frm.remove_custom_button(__('Work Order / Subcontract PO'), __('Create'));
	},

	make_so(frm) {
		frappe.model.open_mapped_doc({
			method: "bartakke_erp.bartakke_erp.api.production_plan.make_so",
			frm: frm
		});
	},

	make_production_process_tracking(frm) {
		frappe.model.open_mapped_doc({
			method: "bartakke_erp.bartakke_erp.api.wo.create_production_process_tracking",
			frm: frm
		});
	},

	custom_selected_item_remove(frm) {
		recalculate_wo_metrics(frm);
	},

});

function recalculate_wo_metrics(frm) {
	if (frm.doc.docstatus === 1) {
		return;
	}

	clearTimeout(frm._wo_metrics_timer);
	frm._wo_metrics_timer = setTimeout(() => {
		frappe.call({
			method: "bartakke_erp.bartakke_erp.api.production_plan.recalculate_work_order_metrics",
			args: { doc: frm.doc },
			freeze: false,
		}).then((r) => {
			if (!r.message) {
				return;
			}

			frm.set_value("custom_wo_weight_", r.message.custom_wo_weight_);
			frm.set_value("custom_area", r.message.custom_area);

			frm.clear_table("custom_assembly_item");
			(r.message.custom_assembly_item || []).forEach((row) => {
				const child = frm.add_child("custom_assembly_item");
				Object.assign(child, row);
			});
			frm.refresh_field("custom_assembly_item");
		});
	}, 300);
}

frappe.ui.form.on("Selected Items", {
	item_code(frm) {
		recalculate_wo_metrics(frm);
	},

	bom_no(frm) {
		recalculate_wo_metrics(frm);
	},

	required_qty(frm) {
		recalculate_wo_metrics(frm);
	},

	planned_qty(frm) {
		recalculate_wo_metrics(frm);
	},
});

frappe.ui.form.on("Production Plan Item", {
	planned_qty(frm) {

		if (!frm.doc.po_items || !frm.doc.po_items.length) return;

		frappe.dom.freeze("Recalculating...");

		frappe.call({
			method: "erpnext.manufacturing.doctype.production_plan.production_plan.get_items_for_material_requests",
			args: {
				doc: frm.doc,
				warehouses: frm.doc.for_warehouse ? [{ warehouse: frm.doc.for_warehouse }] : []
			}
		}).then(r => {

			if (r.message) {
				frm.clear_table("mr_items");

				r.message.forEach(row => {
					let d = frm.add_child("mr_items");
					Object.assign(d, row);
				});

				frm.refresh_field("mr_items");
			}

		}).always(() => {
			frappe.dom.unfreeze();
		});

	}
});
