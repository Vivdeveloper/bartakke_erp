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
