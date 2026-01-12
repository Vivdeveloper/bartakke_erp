// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Store Item", {
	refresh(frm) {
		if (!frm.is_new()) {
			// Check if Item exists for this Store Item
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Item",
					filters: {
						custom_store_item: frm.doc.name
					},
					fields: ["name"],
					limit: 1
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						let item_name = r.message[0].name;
						frm.dashboard.add_comment(__("Item {0} is linked to this Store Item", [item_name.bold()]), "blue", true);

						// Add button to view the Item
						frm.add_custom_button(__("View Item"), function() {
							frappe.set_route("Form", "Item", item_name);
						});
					}
				}
			});
		}
	}
});