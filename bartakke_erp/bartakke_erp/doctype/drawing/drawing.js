// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.ui.form.on("Drawing", {
// 	refresh(frm) {

// 	},
});

frappe.ui.form.on("Drawing Revision", {

    redirect(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.file_url) {

            let url = `/api/method/bartakke_erp.bartakke_erp.doctype.drawing_sync_tool.drawing_sync_tool.open_local_file?file_name=${encodeURIComponent(row.file_url)}`;

            window.open(url, "_blank", "noopener,noreferrer");
        }
    },

    dxf_redirect(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.dxf_file_url) {

            let url = `/api/method/bartakke_erp.bartakke_erp.doctype.drawing_sync_tool.drawing_sync_tool.open_local_file?file_name=${encodeURIComponent(row.dxf_file_url)}`;

            window.open(url, "_blank", "noopener,noreferrer");
        }
    }

});