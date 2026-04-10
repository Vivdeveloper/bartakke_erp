// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

function set_custom_indent_from_rows(frm) {
	if (frm.doc.custom_indent) {
		return;
	}

	let indent = null;
	(frm.doc.material_requests || []).some((row) => {
		if (row.material_request) {
			indent = row.material_request;
			return true;
		}
		return false;
	});

	if (!indent) {
		(frm.doc.po_items || []).some((row) => {
			if (row.material_request) {
				indent = row.material_request;
				return true;
			}
			return false;
		});
	}

	if (indent) {
		frm.doc.custom_indent = indent;
		frm.refresh_field('custom_indent')
	}
}

frappe.ui.form.on("Production Plan", {
	onload(frm) {
		if (!frm.is_new() || !frappe.route_options) {
			return;
		}

		const material_request = frappe.route_options.material_request;
		if (material_request) {
			frm.set_value("get_items_from", "Material Request");
			if (!frm.doc.material_requests || frm.doc.material_requests.length === 0) {
				const row = frm.add_child("material_requests");
				row.material_request = material_request;
				frm.refresh_field("material_requests");
			}
			frm.set_value("custom_indent", material_request);
		}

		frappe.route_options = null;
	},
	refresh(frm) {
		set_custom_indent_from_rows(frm);

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__('Sales Order'),
				() => {
					frm.trigger('make_so');
				},
				__('Create')
			);
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__('Production Process Tracking'),
				() => {
					frm.trigger('make_production_process_tracking');
				},
				__('Create')
			);
		}
		frm.remove_custom_button(
    __('Work Order / Subcontract PO'),
			__('Create')
		);
		if (frm.doc.mr_items.length === 0){
			frm.events.get_items_for_material_requests(frm, [
							{
								warehouse: 'Unit-1 - BEPL',
							},
						]);
		}
		if (frm.doc.sub_assembly_items.length === 0){
			frm.trigger('get_sub_assembly_items')
		}

	},

	make_so(frm) {
		frappe.model.open_mapped_doc({
			method: "bartakke_erp.bartakke_erp.api.production_plan.make_so",
			frm: frm,
			freeze: true,
			freeze_message: __("Creating Sales Order...")
		});
	},

	material_requests(frm) {
		set_custom_indent_from_rows(frm);
	},
	po_items(frm) {
		set_custom_indent_from_rows(frm);
	},
	make_production_process_tracking(frm) {
		frappe.model.open_mapped_doc({
			method: "bartakke_erp.bartakke_erp.api.wo.create_production_process_tracking",
			frm: frm,
			freeze: true,
			freeze_message: __("Creating Production Process Tracking...")
		});
	},
	after_save(frm) {

		if (frm._assembly_loaded) return;

		let items = frm.doc.sub_assembly_items.filter(row => row.bom_no);

		if (!items.length) return;

		frm._assembly_loaded = true;

		frappe.call({
			method: "bartakke_erp.bartakke_erp.api.production_plan.add_assembly_items",
			args: {
				pp_name: frm.doc.name,
				items: items
			},
			freeze: true,
			freeze_message: __("Fetching Assembly Items...")
		}).then(r => {

			if (!r.message) return;

			frm.clear_table("custom_assembly_item");

			r.message.forEach(item => {

				let child = frm.add_child("custom_assembly_item");

				child.item_code = item.item_code;
				child.item_name = item.item_name;
				child.item_description = item.item_description;
				child.uom = item.uom;
				child.qty = item.qty;
				frappe.db.get_value("Item", item.item_code,
					["custom_full_drawing_number_", "custom_development_size_a", "custom_development_size_b", "custom_area", "weight_per_unit", "custom_t", "item_group"]
				).then(r => {

					child.full_drawing_no = r.message.custom_full_drawing_number_;
					child.development_size_a = r.message.custom_development_size_a;
					child.development_size_b = r.message.custom_development_size_b;
					child.area = r.message.custom_area
					child.weight_per_unit = r.message.weight_per_unit
					child.thickness_in_mm = r.message.custom_t
					child.item_group = r.message.item_group

				});

			});

			frm.refresh_field("custom_assembly_item");

		});

	},

	get_sub_assembly_items(frm) {
		frm.dirty();

		frappe.call({
			method: "get_sub_assembly_items",
			freeze: true,
			doc: frm.doc,
			callback: function () {
				refresh_field("sub_assembly_items");
			},
		});
	},
	get_items_for_material_requests(frm, warehouses) {
		frappe.call({
			method: "erpnext.manufacturing.doctype.production_plan.production_plan.get_items_for_material_requests",
			freeze: true,
			args: {
				doc: frm.doc,
				warehouses: warehouses || [],
			},
			callback: function (r) {
				console.log("wareho", warehouses)
				if (r.message) {
					frm.set_value("mr_items", []);
					r.message.forEach((row) => {
						let d = frm.add_child("mr_items");
						for (let field in row) {
							if (field !== "name") {
								d[field] = row[field];
							}
						}
					});
				}
				refresh_field("mr_items");
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
	}
});
