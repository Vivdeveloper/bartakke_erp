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
        calculate_totals(frm);
    },
    production_process_tracking_item_remove: function(frm) {
        calculate_totals(frm);
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

function calculate_totals(frm) {
    let wt = 0;
    let area = 0;

    (frm.doc.production_process_tracking_item || []).forEach(i => {
        wt += flt(i.weight_kg);
        area += flt(i.area_sq_mtr_paint);
    });

    frm.set_value('weight_kg', wt);
    frm.set_value('area_sq_mtr_paint', area);
}