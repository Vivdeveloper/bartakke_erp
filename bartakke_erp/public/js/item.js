frappe.ui.form.on("Item", {
    refresh(frm) {
        frm._drawing_counter_item_group = frm.doc.item_group || "";
    },

    custom_add_drawing(frm) {
        if (!frm.doc.custom_drawing_no) {
            frappe.call({
                method: "bartakke_erp.bartakke_erp.api.item.get_drawing",
                args: { doc: frm.doc },
                callback(r) {
                    if (r.message !== undefined && r.message !== null && r.message !== "") {
                        frm.set_value("custom_drawing_no", r.message);
                    }
                },
            });
        }
    },

    item_group(frm) {
        const cur = frm.doc.item_group || "";

        if (frm._drawing_counter_item_group === undefined) {
            frm._drawing_counter_item_group = cur;
            return;
        }

        const prev = frm._drawing_counter_item_group;
        if (cur === prev) {
            return;
        }

        if (!cur) {
            frm._drawing_counter_item_group = "";
            frm.set_value("custom_drawing_no", "");
            return;
        }

        frappe.call({
            method: "bartakke_erp.bartakke_erp.api.item.get_drawing",
            args: { doc: frm.doc },
            callback(r) {
                if (r.message !== undefined && r.message !== null && r.message !== "") {
                    frm.set_value("custom_drawing_no", r.message);
                } else {
                    frm.set_value("custom_drawing_no", "");
                }
                frm._drawing_counter_item_group = cur;
            },
        });
    },

    after_save(frm) {
        frappe.call({
            method: "bartakke_erp.bartakke_erp.api.item.get_revision",
            args: { doc: frm.doc },
            callback(r) {
                if (r.message) {
                    frm.set_value("custom_revision", r.message);
                }
            },
        });
    },
});
