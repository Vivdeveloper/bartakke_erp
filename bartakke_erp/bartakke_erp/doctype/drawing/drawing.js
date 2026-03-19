// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Drawing", {
// 	refresh(frm) {

// 	},
});

frappe.ui.form.on("Drawing Revision", {
    redirect(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.file_url){
            window.open(row.file_url, "_blank")
        }
    },
});
