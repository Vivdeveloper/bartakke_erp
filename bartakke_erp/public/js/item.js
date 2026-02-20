frappe.ui.form.on('Item', {
    custom_add_drawing: function (frm) {
        if (!frm.doc.custom_drawing_no) {
            frappe.call({
            method: "bartakke_erp.bartakke_erp.api.item.get_drawing",
            args: {
                doc: frm.doc
            },
            callback(r) {
                if (r.message) {
                    frm.set_value("custom_drawing_no", r.message);
                }
            }

        })
        }
        
    },
    custom_sf_code: function (frm) {
        if (!frm.doc.custom_drawing_no && frm.doc.item_code && frm.doc.item_group) {
            frappe.call({
            method: "bartakke_erp.bartakke_erp.api.item.get_drawing",
            args: {
                doc: frm.doc
            },
            callback(r) {
                if (r.message) {
                    frm.set_value("custom_drawing_no", r.message);
                }
            }

        })
        }
        
    },
    custom_add_revision: function (frm) {
        console.log('ass')
        frappe.call({
            method: "bartakke_erp.bartakke_erp.api.item.get_revision",
            args: {
                doc: frm.doc
            },
            callback(r) {
                if (r.message) {
                    frm.set_value("custom_revision", r.message);
                }
            }

        })
    }
})