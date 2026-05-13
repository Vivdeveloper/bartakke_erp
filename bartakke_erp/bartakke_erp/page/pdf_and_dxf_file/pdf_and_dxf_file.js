// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.provide("bartakke_erp.pages");

const MODULE = "bartakke_erp.bartakke_erp.page.pdf_and_dxf_file.pdf_and_dxf_file";

function rpc(method, args) {
	return frappe.xcall(`${MODULE}.${method}`, args || {});
}

/** Desk page: button above each URL (Auto Search / Source, Revision / Target), scanned grid. */
bartakke_erp.pages.PdfAndDxfFilePage = class PdfAndDxfFilePage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = null;
		this.controls = {};
		this.$tbody = null;
	}

	init() {
		this.page = frappe.ui.make_app_page({
			parent: this.wrapper,
			title: __("PDF and DXF File"),
			single_column: true,
		});
		this.$main = $(this.page.main);

		this._fields();
		this._table();
		rpc("get_page_state").then((st) => this._apply(st));
	}

	_fields() {
		const $wrap = $('<div class="p-3"><div class="row"/></div>').appendTo(this.$main);
		const $row = $wrap.find(".row");

		const $srcCol = $('<div class="col-md-6"/>').appendTo($row);
		$('<button type="button" class="btn btn-primary btn-sm mb-2"/>')
			.text(__("Auto Search"))
			.on("click", () => this.auto_search())
			.appendTo($srcCol);
		const srcCtrl = frappe.ui.form.make_control({
			df: { fieldname: "source_url", fieldtype: "Data", label: __("Source URL"), read_only: 1 },
			parent: $srcCol,
			render_input: true,
		});
		srcCtrl.refresh();
		this.controls.source_url = srcCtrl;

		const $tgtCol = $('<div class="col-md-6"/>').appendTo($row);
		$('<button type="button" class="btn btn-default btn-sm mb-2"/>')
			.text(__("Revision"))
			.on("click", () => this.move_to_target())
			.appendTo($tgtCol);
		const tgtCtrl = frappe.ui.form.make_control({
			df: { fieldname: "target_url", fieldtype: "Data", label: __("Target URL"), read_only: 1 },
			parent: $tgtCol,
			render_input: true,
		});
		tgtCtrl.refresh();
		this.controls.target_url = tgtCtrl;
	}

	_table() {
		const $w = $(
			'<div class="px-3 pb-3"><h6 class="text-muted mb-2"></h6><table class="table table-bordered"><thead><tr></tr></thead><tbody></tbody></table></div>'
		).appendTo(this.$main);
		$w.find("h6").text(__("Scanned files"));
		const cols = [__("File Name"), __("PDF"), __("DXF"), __("Item code")];
		const $tr = $w.find("thead tr");
		cols.forEach((t) => $tr.append($("<th/>").text(t)));
		this.$tbody = $w.find("tbody");
	}

	_vals() {
		return {
			source_url: (this.controls.source_url.get_value() || "").trim(),
			target_url: (this.controls.target_url.get_value() || "").trim(),
		};
	}

	auto_search() {
		if (!this._vals().source_url) {
			frappe.msgprint(__("Set Source URL in PDF and DXF File Settings."));
			return;
		}
		frappe.dom.freeze(__("Searching…"));
		rpc("save_page_urls", this._vals())
			.then(() => rpc("auto_search_files"))
			.then((data) => this._done(data))
			.catch((err) => {
				frappe.show_alert({ message: err.message || __("Search failed"), indicator: "red" });
			})
			.finally(() => frappe.dom.unfreeze());
	}

	move_to_target() {
		frappe.confirm(
			__("Move scanned files to the Target folder? This cannot be undone."),
			() => {
				frappe.dom.freeze(__("Moving…"));
				rpc("move_files_to_target")
					.then((data) => this._done(data))
					.catch((err) => {
						frappe.show_alert({ message: err.message || __("Move failed"), indicator: "red" });
					})
					.finally(() => frappe.dom.unfreeze());
			},
			() => {}
		);
	}

	_done(data) {
		this._apply(data);
		frappe.show_alert({
			message: (data && data.message) || __("Done"),
			indicator: "green",
		});
	}

	_apply(data) {
		if (!data) return;
		this.controls.source_url.set_value(data.source_url || "");
		this.controls.target_url.set_value(data.target_url || "");
		this._rows(data.pdf_and_dxf_file_items || []);
	}

	/** Group by sf-drawing-rev (e.g. 11-17384-1); names like '11-17384-1 copy' share one row. */
	_tripleKey(stem) {
		const s = String(stem || "").trim();
		const m = s.match(/^(\d+-\d+-\d+)/);
		return m ? m[1] : s;
	}

	_group(rows) {
		const m = new Map();
		for (const row of rows) {
			const fn = (row.file_name || "").trim();
			const ext = (row.extension || "").toLowerCase();
			const raw = fn.replace(/\.(pdf|dxf)$/i, "") || fn;
			const key = this._tripleKey(raw);
			if (!m.has(key)) m.set(key, { stem: key, pdf: null, dxf: null });
			const g = m.get(key);
			if (ext === "pdf") g.pdf = g.pdf || row;
			else if (ext === "dxf") g.dxf = g.dxf || row;
		}
		return Array.from(m.values()).sort((a, b) => String(a.stem).localeCompare(String(b.stem)));
	}

	_rows(rows) {
		const esc = frappe.utils.escape_html;
		if (!rows.length) {
			this.$tbody.html(
				`<tr><td colspan="4" class="text-muted text-center">${esc(__("No Data"))}</td></tr>`
			);
			return;
		}
		const body = this._group(rows)
			.map((g) => {
				const ref = g.pdf || g.dxf || {};
				const ic = esc((ref.item_code || "").trim());
				return `<tr>
					<td class="ellipsis" title="${esc(g.stem)}">${esc(g.stem)}</td>
					<td class="ellipsis">${esc((g.pdf && g.pdf.file_name) || "")}</td>
					<td class="ellipsis">${esc((g.dxf && g.dxf.file_name) || "")}</td>
					<td class="ellipsis" title="${ic}">${ic}</td>
				</tr>`;
			})
			.join("");
		this.$tbody.html(body);
	}
};

frappe.pages["pdf-and-dxf-file"].on_page_load = function (wrapper) {
	new bartakke_erp.pages.PdfAndDxfFilePage(wrapper).init();
};
