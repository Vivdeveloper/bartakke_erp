function set_custom_indent_from_rows(frm) {
	if (frm.doc.custom_indent) return;

	let indent = null;

	(frm.doc.material_requests || []).some((row) => {
		if (row.material_request) {
			indent = row.material_request;
			return true;
		}
	});

	if (!indent) {
		(frm.doc.po_items || []).some((row) => {
			if (row.material_request) {
				indent = row.material_request;
				return true;
			}
		});
	}

	if (indent && frm.doc.custom_indent !== indent) {
		frm.set_value("custom_indent", indent);
	}
}

frappe.ui.form.on("Production Plan", {

	onload(frm) {
		if (!frm.is_new() || !frappe.route_options) return;

		const material_request = frappe.route_options.material_request;

		if (material_request) {
			frm.set_value("get_items_from", "Material Request");

			if (!frm.doc.material_requests || frm.doc.material_requests.length === 0) {
				let row = frm.add_child("material_requests");
				row.material_request = material_request;
				frm.refresh_field("material_requests");
			}

			frm.set_value("custom_indent", material_request);
		}

		frappe.route_options = null;
	},

	refresh(frm) {

		if (!frm._indent_set) {
			set_custom_indent_from_rows(frm);
			frm._indent_set = true;
		}

		if (frm.doc.docstatus === 1) {

			frm.add_custom_button(__('Sales Order'), () => {
				frm.trigger('make_so');
			}, __('Create'));

			frm.add_custom_button(__('Production Process Tracking'), () => {
				frm.trigger('make_production_process_tracking');
			}, __('Create'));
		}

		frm.remove_custom_button(__('Work Order / Subcontract PO'), __('Create'));
	},

	onload_post_render(frm) {

		if (frm._mr_loaded) return;

		if (!frm.is_new() && (!frm.doc.mr_items || frm.doc.mr_items.length === 0)) {
			frm._mr_loaded = true;

			frm.events.get_items_for_material_requests(frm, [
				{ warehouse: 'Unit-1 - BEPL' }
			]);
		}
	},

	before_save(frm) {

		let items = (frm.doc.sub_assembly_items || []).filter(row => row.bom_no);
		if (!items.length) return;

		if (frm._assembly_processing) return;
		frm._assembly_processing = true;

		return frappe.call({
			method: "bartakke_erp.bartakke_erp.api.production_plan.add_assembly_items",
			args: {
				pp_name: frm.doc.name,
				items: items
			},
			async: false  
		}).then(r => {

			if (!r.message) return;

			let current = JSON.stringify(frm.doc.custom_assembly_item || []);
			let incoming = JSON.stringify(r.message);

			if (current === incoming) return;

			frm.clear_table("custom_assembly_item");

			r.message.forEach(item => {
				let child = frm.add_child("custom_assembly_item");
				Object.assign(child, item);
			});
		});
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

	material_requests(frm) {
		set_custom_indent_from_rows(frm);
	},

	po_items(frm) {
		set_custom_indent_from_rows(frm);
	},

	get_items_for_material_requests(frm, warehouses) {
		frappe.call({
			method: "erpnext.manufacturing.doctype.production_plan.production_plan.get_items_for_material_requests",
			args: {
				doc: frm.doc,
				warehouses: warehouses || [],
			},
			callback: function (r) {

				if (!r.message) return;

				let current = JSON.stringify(frm.doc.mr_items || []);
				let incoming = JSON.stringify(r.message);

				if (current === incoming) return;

				frm.clear_table("mr_items");

				r.message.forEach((row) => {
					let d = frm.add_child("mr_items");
					Object.assign(d, row);
				});

				frm.refresh_field("mr_items");
			},
		});
	},
});

frappe.ui.form.on("Production Plan Material Request", {
	material_request(frm) {
		set_custom_indent_from_rows(frm);
	}
});

frappe.ui.form.on("Production Plan Item", {
	material_request(frm) {
		set_custom_indent_from_rows(frm);
	},
	planned_qty: frappe.utils.debounce(function (frm) {

		if (!frm.doc.po_items || !frm.doc.po_items.length) return;

		frappe.dom.freeze("Recalculating...");

		// ---------- Sub Assembly ----------
		frappe.call({
			method: "bartakke_erp.bartakke_erp.api.production_plan.recalculate_sub_assembly",
			args: {
				doc: frm.doc
			}
		}).then(r => {

			if (r.message) {
				frm.clear_table("sub_assembly_items");

				r.message.forEach(row => {
					let d = frm.add_child("sub_assembly_items");
					Object.assign(d, row);
				});

				frm.refresh_field("sub_assembly_items");
			}

			// ---------- Raw Materials ----------
			return frappe.call({
				method: "bartakke_erp.bartakke_erp.api.production_plan.custom_get_items_for_material_requests",
				args: {
					doc: frm.doc,
					warehouses: frm.doc.for_warehouse
						? [frm.doc.for_warehouse]
						: []
				}
			});

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

	}, 500)
});

frappe.ui.form.on('Production Plan', {
	refresh(frm) {
		// your code here
	}
})
