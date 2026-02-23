frappe.ui.form.on('Production Process Tracking', {
    setup(frm) {
        frm.set_query("item", function (doc) {
			return {
				query: "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.get_assembly_items",
				filters: { work_order_no: frm.doc.work_order_no },
			};
		});
    },
    qty(frm) {
        if (!frm.doc.area_sq_mtr_paint && frm.doc.qty) {
            frappe.db.get_value("Item", { name: frm.doc.item }, ["custom_area", "weight_per_unit"], (r) => {
			frm.set_value("area_sq_mtr_paint", r.custom_area * frm.doc.qty);
            frm.set_value("weight_kg", r.weight_per_unit * frm.doc.qty)
		});
        }
    }
})