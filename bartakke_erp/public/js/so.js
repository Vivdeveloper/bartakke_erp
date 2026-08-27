frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (!frm.doc.customer) return;

        frm.add_custom_button(__('Production Plan'), () => {
            open_production_plan_dialog(frm);
        }, __('Get Items From'));

        if (!frm.is_new()) {
            frm.add_custom_button(__('Proforma Invoice'), () => {
                frappe.model.open_mapped_doc({
                    method: 'bartakke_erp.bartakke_erp.api.proforma_invoice.make_proforma_invoice',
                    frm: frm,
                });
            }, __('Create'));
        }
    }
});

function open_production_plan_dialog(frm) {
    frappe.call({
        method: "bartakke_erp.bartakke_erp.api.production_plan.get_production_plans",
        args: {
            customer: frm.doc.customer
        },
        callback: function (r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint("No Production Plans found");
                return;
            }

            // ✅ initialize select field
            r.message.forEach(d => {
                d.select = 0;
            });

            let dialog = new frappe.ui.Dialog({
                title: "Select Production Plan Items",
                size: "large",
                fields: [
                    {
                        fieldname: "items",
                        fieldtype: "Table",
                        label: "Items",
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: r.message,
                        fields: [
                            // {
                            //     fieldname: "select",
                            //     fieldtype: "Check",
                            //     label: "Select",
                            //     in_list_view: 1
                            // },
                            {
                                fieldname: "production_plan",
                                fieldtype: "Data",
                                label: "Production Plan",
                                in_list_view: 1,
                                read_only: 1
                            },
                            {
                                fieldname: "item_code",
                                fieldtype: "Data",
                                label: "Item",
                                in_list_view: 1,
                                read_only: 1
                            },
                            {
                                fieldname: "qty",
                                fieldtype: "Float",
                                label: "Qty",
                                in_list_view: 1
                            }
                        ]
                    }
                ],
                primary_action_label: "Add to Sales Order",
                primary_action() {

    let grid = dialog.fields_dict.items.grid;

    // ✅ use built-in selection
    let selected = grid.get_selected_children();

    // 🔁 fallback (important for some versions)
    if (!selected.length) {
        selected = grid.grid_rows
            .filter(row => row.is_selected())
            .map(row => row.doc);
    }

    if (!selected.length) {
        frappe.msgprint("Please select rows using checkbox");
        return;
    }

    selected.forEach(d => {

        let exists = frm.doc.items.some(i => 
            i.item_code === d.item_code &&
            i.production_plan === d.production_plan
        );

        if (!exists) {
            let row = frm.add_child("items");

            row.item_code = d.item_code;
            row.qty = d.qty;

            row.custom_work_order = d.production_plan;
            row.material_request = d.indent;

            if (d.work_order) {
                row.work_order = d.work_order;
            }

            frm.script_manager.trigger("item_code", row.doctype, row.name);
        }
    });

    frm.refresh_field("items");
    dialog.hide();
}
            });

            dialog.show();

            // ✅ remove default grid checkbox column
            let grid = dialog.fields_dict.items.grid;
            grid.df.selectable = false;
            grid.refresh();
        }
    });
}