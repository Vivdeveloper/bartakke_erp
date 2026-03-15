frappe.ui.form.on('Production Process Tracking', {
    setup(frm) {
        frm.set_query("item", function (doc) {
			return {
				query: "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.get_assembly_items",
				filters: { work_order_no: frm.doc.work_order_no },
			};
		});
    },
    refresh(frm) {
        if (frm.doc.work_order_no){
            frappe.call({
                method: "bartakke_erp.bartakke_erp.api.wo.get_assembly_item_details",
                args: {
                    work_order: frm.doc.work_order_no
                },
                callback: function(r) {
                    if (r.message) {
                        console.log("Total Area:", r.message.total_area);
                        console.log("Total Weight:", r.message.total_weight);

                        frm.set_value("area_sq_mtr_paint", r.message.total_area);
                        frm.set_value("weight_kg", r.message.total_weight);
                    }
                }
        });
        }
    },
    qty(frm) {
        if (!frm.doc.area_sq_mtr_paint && frm.doc.qty) {
            frappe.db.get_value("Item", { name: frm.doc.item }, ["custom_area", "weight_per_unit"], (r) => {
			frm.set_value("area_sq_mtr_paint", r.custom_area * frm.doc.qty);
            frm.set_value("weight_kg", r.weight_per_unit * frm.doc.qty)
		});
        }
    },
    item(frm) {
        frappe.db.get_value("Item", { name: frm.doc.item }, "custom_design", (r) => {
            frm.set_value("design", r.custom_design);
        });
        // frappe.db.get_value("Production Plan Item", { parent: frm.doc.work_order_no }, "planned_qty", (r) => {
        //     frm.set_value("work_order_qty", r.planned_qty);
        // });
        frappe.call({
            method: "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.get_planned_qty",
            args: {
                work_order_no: frm.doc.work_order_no
            },
            callback: (r) => {
                if (r.message) {
                    frm.set_value("work_order_qty", r.message);
                }
            }
        });
    },
    qty(frm) {
        if (frm.doc.qty > frm.doc.work_order_qty) {
            frappe.throw("Qty cannot be greater than Work Order Qty")
        }
    }
})