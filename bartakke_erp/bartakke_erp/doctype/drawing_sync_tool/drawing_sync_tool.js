// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Drawing Sync Tool", {
    search_options: function(frm) {
        if (!frm.doc.url) {
            frappe.msgprint("Please enter URL");
            return;
        }

        frappe.call({
            method: "bartakke_erp.bartakke_erp.doctype.drawing_sync_tool.drawing_sync_tool.fetch_missing_drawings",
            args: {
                docname: frm.doc.name
            },
            freeze: true,
            freeze_message: "Fetching drawings...",
            callback: function(r) {
                frm.reload_doc();
            }
        });
    }
});
