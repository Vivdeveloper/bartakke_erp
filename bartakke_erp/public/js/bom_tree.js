// preserve original
if (!frappe.treeview_settings["BOM"]._original_onrender) {
    frappe.treeview_settings["BOM"]._original_onrender =
        frappe.treeview_settings["BOM"].onrender;
}

// extend
frappe.treeview_settings["BOM"] = $.extend(
    {},
    frappe.treeview_settings["BOM"],
    {
        onrender: function (node) {

            frappe.treeview_settings["BOM"]._original_onrender(node);

            setTimeout(() => {

                if (!node.$tree_link) return;

                if (
                    node.data &&
                    node.data.value &&
                    Number(node.data.custom_incomplete) === 1
                ) {
                    console.log('nd', $('.tree-link.selected'))
                    $('.tree-link.selected')
                        .find(".tree-label")
                        .css({
                            "color": "red",
                            "font-weight": "bold"
                        });
                }

            }, 50);
        }
    }
);