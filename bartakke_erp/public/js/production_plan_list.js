frappe.listview_settings['Production Plan'] = {
    onload: function(listview) {
        listview.page.add_action_item(__('Lot Generation'), async function() {

            let selected = listview.get_checked_items();

            if (!selected.length) {
                frappe.msgprint("Please select at least one Work Order");
                return;
            }

            let names = selected.map(doc => doc.name);

            frappe.call({
                method: "bartakke_erp.bartakke_erp.api.wo.create_production_tracking",
                args: {
                    work_orders: names
                },
                freeze: true,
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint("Production Process Tracking Created: " + r.message);
                        frappe.set_route("Form", "Production Process Tracking", r.message);
                    }
                }
            });

        });
    }
};
