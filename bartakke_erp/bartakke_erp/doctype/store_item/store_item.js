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
						// Item exists - show view button
						let item_name = r.message[0].name;
						frm.dashboard.add_comment(__("Item {0} is linked to this Store Item", [item_name.bold()]), "blue", true);

						frm.add_custom_button(__("View Item"), function() {
							frappe.set_route("Form", "Item", item_name);
						});
					} else {
						// Item doesn't exist - show create button
						frm.dashboard.add_comment(__("No Item linked to this Store Item"), "orange", true);

						frm.add_custom_button(__("Create Item"), function() {
							frappe.confirm(
								__("Create Item with code {0}?", [frm.doc.name.bold()]),
								function() {
									frappe.call({
										method: "bartakke_erp.bartakke_erp.doctype.store_item.store_item.create_item_from_store_item",
										args: {
											store_item_name: frm.doc.name
										},
										freeze: true,
										freeze_message: __("Creating Item..."),
										callback: function(response) {
											if (response.message) {
												frappe.show_alert({
													message: __("Item created successfully"),
													indicator: "green"
												});
												setTimeout(function() {
													frm.reload_doc();
												}, 1000);
											}
										}
									});
								}
							);
						}, __("Actions"));
					}
				}
			});
		}
	},
	item_group(frm) {
		frappe.db.get_value("Item Group", { name: frm.doc.item_group }, "parent_item_group", (r) => {
				if (r.parent_item_group == 'Repairs Maint M/C') {
					frm.set_value('stock_type_code', 6)
				}
			});
	}
});