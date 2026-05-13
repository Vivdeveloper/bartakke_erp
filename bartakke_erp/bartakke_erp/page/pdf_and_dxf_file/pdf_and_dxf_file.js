// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.provide("bartakke_erp.pages");

const PDF_DXF_MODULE =
	"bartakke_erp.bartakke_erp.page.pdf_and_dxf_file.pdf_and_dxf_file";

function pdf_dxf_call(method, args) {
	return frappe.xcall(`${PDF_DXF_MODULE}.${method}`, args || {});
}

/**
 * Desk page: read-only URLs, Auto Search, Revision (move to target), scanned table with Item code.
 */
bartakke_erp.pages.PdfAndDxfFilePage = class PdfAndDxfFilePage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = null;
		this.controls = {};
		this._table_body = null;
	}

	init() {
		this.page = frappe.ui.make_app_page({
			parent: this.wrapper,
			title: __("PDF and DXF File"),
			single_column: true,
		});

		this._build_field_area();
		this._build_results_table();

		this._fetch_state();
	}

	_build_field_area() {
		const parent = document.createElement("div");
		parent.className = "p-3";
		this.page.main[0].appendChild(parent);

		const add_data = (fieldname, label, cellParent) => {
			const c = frappe.ui.form.make_control({
				df: {
					fieldname,
					fieldtype: "Data",
					label: __(label),
					read_only: 1,
				},
				parent: cellParent,
				render_input: true,
			});
			c.refresh();
			this.controls[fieldname] = c;
		};

		const rowUrls = document.createElement("div");
		rowUrls.className = "row";
		parent.appendChild(rowUrls);

		const srcCol = document.createElement("div");
		srcCol.className = "col-md-6";
		rowUrls.appendChild(srcCol);
		const tgtCol = document.createElement("div");
		tgtCol.className = "col-md-6";
		rowUrls.appendChild(tgtCol);

		add_data("source_url", __("Source URL"), srcCol);
		add_data("target_url", __("Target URL"), tgtCol);

		const rowBtns = document.createElement("div");
		rowBtns.className = "row mt-2";
		parent.appendChild(rowBtns);

		const searchCol = document.createElement("div");
		searchCol.className = "col-md-6";
		rowBtns.appendChild(searchCol);
		const search_btn = document.createElement("button");
		search_btn.type = "button";
		search_btn.className = "btn btn-primary btn-sm";
		search_btn.textContent = __("Auto Search");
		search_btn.addEventListener("click", () => this.auto_search());
		searchCol.appendChild(search_btn);

		const revCol = document.createElement("div");
		revCol.className = "col-md-6";
		rowBtns.appendChild(revCol);
		const rev_btn = document.createElement("button");
		rev_btn.type = "button";
		rev_btn.className = "btn btn-default btn-sm";
		rev_btn.textContent = __("Revision");
		rev_btn.addEventListener("click", () => this.revision_move_to_target());
		revCol.appendChild(rev_btn);
	}

	_build_results_table() {
		const wrap = document.createElement("div");
		wrap.className = "px-3 pb-3 pt-0";
		this.page.main[0].appendChild(wrap);

		const title = document.createElement("h6");
		title.className = "text-muted mb-2";
		title.textContent = __("Scanned files");
		wrap.appendChild(title);

		const table = document.createElement("table");
		table.className = "table table-bordered";
		wrap.appendChild(table);

		const thead = document.createElement("thead");
		const hr = document.createElement("tr");
		for (const col of [
			__("File Name"),
			__("PDF"),
			__("DXF"),
			__("Item code"),
		]) {
			const th = document.createElement("th");
			th.textContent = col;
			hr.appendChild(th);
		}
		thead.appendChild(hr);
		table.appendChild(thead);

		this._table_body = document.createElement("tbody");
		table.appendChild(this._table_body);
	}

	_get_source_value() {
		return (this.controls.source_url.get_value() || "").trim();
	}

	_get_target_value() {
		return (this.controls.target_url.get_value() || "").trim();
	}

	/** Initial load: no overlay (avoids flash on open). */
	_fetch_state() {
		return pdf_dxf_call("get_page_state").then((st) => this._apply_state(st));
	}

	auto_search() {
		if (!this._get_source_value()) {
			frappe.msgprint(__("Please enter Source URL"));
			return Promise.resolve();
		}

		frappe.dom.freeze(__("Searching…"));
		return pdf_dxf_call("save_page_urls", {
			source_url: this._get_source_value(),
			target_url: this._get_target_value(),
		})
			.then(() => pdf_dxf_call("auto_search_files"))
			.then((data) => {
				this._apply_state(data);
				frappe.show_alert({
					message: data.message || __("Done"),
					indicator: "green",
				});
			})
			.catch((err) => {
				frappe.show_alert({
					message: err.message || __("Search failed"),
					indicator: "red",
				});
			})
			.finally(() => frappe.dom.unfreeze());
	}

	revision_move_to_target() {
		frappe.confirm(
			__(
				"Move scanned files into the Target URL folder on the server? This cannot be undone."
			),
			() => {
				frappe.dom.freeze(__("Moving…"));
				return pdf_dxf_call("move_files_to_target")
					.then((data) => {
						this._apply_state(data);
						frappe.show_alert({
							message: data.message || __("Done"),
							indicator: "green",
						});
					})
					.catch((err) => {
						frappe.show_alert({
							message: err.message || __("Move failed"),
							indicator: "red",
						});
					})
					.finally(() => frappe.dom.unfreeze());
			},
			() => {}
		);
	}

	_apply_state(data) {
		if (!data) return;
		if (this.controls.source_url) {
			this.controls.source_url.set_value(data.source_url || "");
		}
		if (this.controls.target_url) {
			this.controls.target_url.set_value(data.target_url || "");
		}
		this._render_rows(data.pdf_and_dxf_file_items || []);
	}

	/** One table row per base name: same stem for `name.pdf` and `name.dxf`. */
	_group_pdf_dxf_rows(rows) {
		const map = new Map();
		for (const row of rows) {
			const fn = (row.file_name || "").trim();
			const ext = (row.extension || "").toLowerCase();
			const stem = fn.replace(/\.(pdf|dxf)$/i, "") || fn;
			if (!map.has(stem)) {
				map.set(stem, { stem, pdf: null, dxf: null });
			}
			const g = map.get(stem);
			if (ext === "pdf") {
				g.pdf = row;
			} else if (ext === "dxf") {
				g.dxf = row;
			}
		}
		return Array.from(map.values()).sort((a, b) =>
			String(a.stem).localeCompare(String(b.stem))
		);
	}

	_render_rows(rows) {
		while (this._table_body.firstChild) {
			this._table_body.removeChild(this._table_body.firstChild);
		}

		if (!rows.length) {
			const tr = document.createElement("tr");
			const td = document.createElement("td");
			td.colSpan = 4;
			td.className = "text-muted text-center";
			td.textContent = __("No Data");
			tr.appendChild(td);
			this._table_body.appendChild(tr);
			return;
		}

		const grouped = this._group_pdf_dxf_rows(rows);
		for (const g of grouped) {
			const ref = g.pdf || g.dxf || {};
			const tr = document.createElement("tr");
			const itemCode = (ref.item_code || "").trim();
			const cells = [
				g.stem,
				g.pdf ? g.pdf.file_name || "" : "",
				g.dxf ? g.dxf.file_name || "" : "",
				itemCode,
			];
			for (const v of cells) {
				const td = document.createElement("td");
				const text = v == null ? "" : String(v);
				td.textContent = text;
				td.className = "ellipsis";
				td.title = text;
				tr.appendChild(td);
			}
			this._table_body.appendChild(tr);
		}
	}
};

frappe.pages["pdf-and-dxf-file"].on_page_load = function (wrapper) {
	frappe.bartakke_pdf_dxf_page = new bartakke_erp.pages.PdfAndDxfFilePage(wrapper);
	frappe.bartakke_pdf_dxf_page.init();
};
