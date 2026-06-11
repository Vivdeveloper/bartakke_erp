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
        setup_work_order_tracking_buttons(frm);
        render_work_order_tracking_html(frm);
    },
    production_process_tracking_item_remove: function(frm) {
        calculate_totals(frm);
    },
    production_process_tracking_item_add: function(frm) {
        calculate_totals(frm);
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

function setup_work_order_tracking_buttons(frm) {
    if (frm.is_new()) {
        return;
    }

    frappe.call({
        method:
            "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.get_work_order_tracking_map",
        args: { source_name: frm.doc.name },
        callback(r) {
            const map = r.message || {};
            const work_orders = Object.keys(map);

            work_orders.forEach((wo_name) => {
                const tracking_name = map[wo_name];
                if (tracking_name) {
                    frm.add_custom_button(
                        wo_name,
                        () => {
                            frappe.set_route(
                                "Form",
                                "Production Process Tracking Work Order",
                                tracking_name
                            );
                        },
                        __("Work Order Tracking")
                    );
                }
            });

            const missing = work_orders.filter((wo_name) => !map[wo_name]);
            if (!missing.length) {
                return;
            }

            frm.add_custom_button(
                __("Generate Work Order Tracking"),
                () => show_work_order_tracking_dialog(frm),
                __("Create")
            );
        },
    });
}

function show_work_order_tracking_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Generate Work Order Tracking"),
        fields: [
            {
                fieldname: "template",
                fieldtype: "Link",
                label: __("Production Process Tracking Template"),
                options: "Production Process Tracking Template",
                reqd: 1,
            },
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
            frappe.call({
                method:
                    "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.create_production_process_tracking_work_orders",
                args: {
                    source_name: frm.doc.name,
                    template: values.template,
                },
                freeze: true,
                freeze_message: __("Creating Work Order Tracking..."),
                callback(res) {
                    d.hide();
                    if (!res.message) {
                        return;
                    }

                    const { created = [], existing = [] } = res.message;
                    let message = "";

                    if (created.length) {
                        message += __("Created: {0}", [created.join(", ")]);
                    }
                    if (existing.length) {
                        message += (message ? "<br>" : "") + __("Already exists: {0}", [
                            existing.join(", "),
                        ]);
                    }

                    frappe.msgprint({
                        title: __("Work Order Tracking"),
                        message,
                        indicator: "green",
                    });

                    if (created.length === 1) {
                        frappe.set_route(
                            "Form",
                            "Production Process Tracking Work Order",
                            created[0]
                        );
                        return;
                    }

                    frm.reload_doc();
                },
            });
        },
    });
    d.show();
}

function render_work_order_tracking_html(frm) {
    const field = frm.fields_dict.production_process_tracking_work_order_html;
    if (!field || frm.is_new()) {
        if (field) {
            field.$wrapper.html("");
        }
        return;
    }

    frappe.call({
        method:
            "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.get_work_order_tracking_dashboard",
        args: { source_name: frm.doc.name },
        callback(r) {
            field.$wrapper.html(build_work_order_tracking_html(r.message || {}));
            bind_work_order_tracking_events(frm, field.$wrapper);
        },
    });
}

function build_work_order_tracking_html(data) {
    const rows = data.rows || [];
    const stage_columns = data.stage_columns || [];

    if (!rows.length) {
        return `<div class="text-muted small">${__("No work orders in this lot.")}</div>`;
    }

    const header_cells = stage_columns
        .map(
            (stage) =>
                `<th class="text-center ppt-wo-matrix-stage">${frappe.utils.escape_html(stage)}</th>`
        )
        .join("");

    const body_rows = rows
        .map((row) => {
            const stage_cells = stage_columns
                .map((stage_name) => {
                    if (!row.tracking_name) {
                        return `<td class="text-center text-muted ppt-wo-matrix-cell">-</td>`;
                    }

                    const stage = (row.stage_map || {})[stage_name];
                    if (!stage) {
                        return `<td class="text-center text-muted ppt-wo-matrix-cell">-</td>`;
                    }

                    const checked = stage.completed ? "checked" : "";
                    const title = stage.completed_by
                        ? `${stage.completed_by}${stage.completed_on ? " | " + frappe.datetime.str_to_user(stage.completed_on) : ""}`
                        : "";
                    return `
                        <td class="text-center ppt-wo-matrix-cell" title="${frappe.utils.escape_html(title)}">
                            <input type="checkbox" class="ppt-wo-stage-check"
                                data-work-order="${frappe.utils.escape_html(row.tracking_name)}"
                                data-stage="${frappe.utils.escape_html(stage.name)}"
                                ${checked}>
                        </td>`;
                })
                .join("");

            const open_link = row.tracking_name
                ? `<a class="small" href="/app/production-process-tracking-work-order/${encodeURIComponent(row.tracking_name)}">${__("Open")}</a>`
                : `<span class="indicator-pill orange small">${__("Not Generated")}</span>`;

            return `
                <tr>
                    <td class="ppt-wo-matrix-wo">
                        <div><strong>${frappe.utils.escape_html(row.work_order_no || "")}</strong></div>
                        ${open_link}
                    </td>
                    <td class="ppt-wo-matrix-item">${frappe.utils.escape_html(row.item || "")}</td>
                    ${stage_cells}
                </tr>`;
        })
        .join("");

    return `
        <style>
            .ppt-wo-matrix { border-collapse: collapse; width: 100%; background: #fff; }
            .ppt-wo-matrix th, .ppt-wo-matrix td {
                border: 1px solid #d1d8dd;
                padding: 8px 10px;
                vertical-align: middle;
            }
            .ppt-wo-matrix thead th {
                background: #f4f5f6;
                font-weight: 600;
            }
            .ppt-wo-matrix-wo { min-width: 120px; white-space: nowrap; }
            .ppt-wo-matrix-item { min-width: 180px; max-width: 280px; }
            .ppt-wo-matrix-stage { min-width: 90px; }
            .ppt-wo-matrix-cell input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
        </style>
        <div class="table-responsive">
            <table class="table table-bordered table-sm ppt-wo-matrix mb-0">
                <thead>
                    <tr>
                        <th>${__("Work Order")}</th>
                        <th>${__("Item")}</th>
                        ${header_cells}
                    </tr>
                </thead>
                <tbody>${body_rows}</tbody>
            </table>
        </div>`;
}

function bind_work_order_tracking_events(frm, $wrapper) {
    $wrapper.off("change.ppt-wo").on("change.ppt-wo", ".ppt-wo-stage-check", function () {
        const $checkbox = $(this);
        const work_order_name = $checkbox.data("work-order");
        const stage_name = $checkbox.data("stage");
        const completed = $checkbox.is(":checked") ? 1 : 0;

        frappe.call({
            method:
                "bartakke_erp.bartakke_erp.doctype.production_process_tracking_work_order.production_process_tracking_work_order.update_work_order_stage",
            args: {
                work_order_name,
                stage_name,
                completed,
            },
            freeze: true,
            error() {
                render_work_order_tracking_html(frm);
            },
            callback() {
                render_work_order_tracking_html(frm);
                frm.reload_doc();
            },
        });
    });
}

function calculate_totals(frm) {
    frappe.call({
        method:
            "bartakke_erp.bartakke_erp.doctype.production_process_tracking.production_process_tracking.get_lot_weight_and_area",
        args: { doc: frm.doc },
        callback(r) {
            if (!r.message) {
                return;
            }
            frm.set_value("weight_kg", r.message.weight_kg);
            frm.set_value("area_sq_mtr_paint", r.message.area_sq_mtr_paint);
        },
    });
}