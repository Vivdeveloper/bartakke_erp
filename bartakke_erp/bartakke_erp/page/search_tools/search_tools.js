// Copyright (c) 2026, Viv Choudhary and contributors
// For license information, please see license.txt

frappe.provide("bartakke_erp.pages");

const MODULE = "bartakke_erp.bartakke_erp.page.search_tools.search_tools";

function rpc(method, args) {
	return frappe.xcall(`${MODULE}.${method}`, args || {});
}

const TABS = [
	{ key: "word_replace", label: __("Word replace"), ready: false },
	{ key: "search_replace", label: __("Search & replace"), ready: false },
	{ key: "search_add", label: __("Search & Add"), ready: false },
	{ key: "search_revision", label: __("Search for Revision"), ready: true },
];

const REVISION_EDITABLE = ["custom_revision", "custom_development_size_a", "custom_development_size_b", "custom_t"];

/** Desk page: tabs for Word replace / Search & replace / Search & Add / Search for Revision. */
bartakke_erp.pages.SearchToolsPage = class SearchToolsPage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = null;
		this.active_tab = "search_revision";
		this.rows = [];
		this.dirty = new Set();
	}

	init() {
		this.page = frappe.ui.make_app_page({
			parent: this.wrapper,
			title: __("Search Tools"),
			single_column: true,
		});
		this.$main = $(this.page.main);

		this._tabs();
		this._body();
		this._render_tab();
	}

	_tabs() {
		const $nav = $('<div class="p-3 pb-0"><ul class="nav nav-pills"></ul></div>').appendTo(this.$main);
		const $ul = $nav.find(".nav-pills");
		this.$tab_links = {};

		TABS.forEach((tab) => {
			const $li = $('<li class="nav-item"/>').appendTo($ul);
			const $a = $('<a class="nav-link" href="#"/>')
				.text(tab.label)
				.on("click", (e) => {
					e.preventDefault();
					this.active_tab = tab.key;
					this._render_tab();
				})
				.appendTo($li);
			this.$tab_links[tab.key] = $a;
		});
	}

	_body() {
		this.$body = $('<div class="px-3 pb-3"/>').appendTo(this.$main);
	}

	_render_tab() {
		Object.entries(this.$tab_links).forEach(([key, $a]) => {
			$a.toggleClass("active", key === this.active_tab);
		});

		const tab = TABS.find((t) => t.key === this.active_tab);
		this.$body.empty();

		if (!tab.ready) {
			$('<div class="text-muted text-center p-5"/>').text(__("Coming soon")).appendTo(this.$body);
			return;
		}

		this._render_search_revision();
	}

	_render_search_revision() {
		const $form = $(
			`<div class="row mb-3">
				<div class="col-md-5"></div>
				<div class="col-md-5"></div>
				<div class="col-md-2 d-flex align-items-end">
					<button type="button" class="btn btn-primary btn-sm search-btn">${frappe.utils.escape_html(__("Search"))}</button>
				</div>
			</div>`
		).appendTo(this.$body);

		this.drawing_ctrl = frappe.ui.form.make_control({
			df: { fieldname: "drawing_no", fieldtype: "Data", label: __("Search By Drawing number") },
			parent: $form.find(".col-md-5").eq(0),
			render_input: true,
		});
		this.drawing_ctrl.refresh();

		this.description_ctrl = frappe.ui.form.make_control({
			df: { fieldname: "description", fieldtype: "Data", label: __("Search By Description") },
			parent: $form.find(".col-md-5").eq(1),
			render_input: true,
		});
		this.description_ctrl.refresh();

		[this.drawing_ctrl, this.description_ctrl].forEach(($ctrl) => {
			$ctrl.$input.on("keydown", (e) => {
				if (e.key === "Enter") this.search();
			});
		});

		$form.find(".search-btn").on("click", () => this.search());

		const $table_wrap = $(
			`<div>
				<table class="table table-bordered">
					<thead><tr>
						<th>${__("Sr no")}</th>
						<th>${__("Description")}</th>
						<th>${__("Material")}</th>
						<th>${__("SF")}</th>
						<th>${__("Drg number")}</th>
						<th>${__("Rev no")}</th>
						<th>${__("Dev size A")}</th>
						<th>${__("Dev size B")}</th>
						<th>${__("Thickness")}</th>
					</tr></thead>
					<tbody></tbody>
				</table>
				<button type="button" class="btn btn-primary btn-sm save-btn" disabled>${frappe.utils.escape_html(__("Save Changes"))}</button>
			</div>`
		).appendTo(this.$body);

		this.$tbody = $table_wrap.find("tbody");
		this.$save_btn = $table_wrap.find(".save-btn").on("click", () => this.save());

		this._rows([]);
	}

	search() {
		const drawing_no = (this.drawing_ctrl.get_value() || "").trim();
		const description = (this.description_ctrl.get_value() || "").trim();

		if (!drawing_no && !description) {
			frappe.msgprint(__("Enter a Drawing number or Description to search."));
			return;
		}

		frappe.dom.freeze(__("Searching…"));
		rpc("search_items_for_revision", { drawing_no, description })
			.then((rows) => this._rows(rows))
			.catch((err) => {
				frappe.show_alert({ message: err.message || __("Search failed"), indicator: "red" });
			})
			.finally(() => frappe.dom.unfreeze());
	}

	_rows(rows) {
		this.rows = rows || [];
		this.dirty = new Set();
		this.$save_btn.prop("disabled", true);

		if (!this.rows.length) {
			this.$tbody.html(
				`<tr><td colspan="9" class="text-muted text-center">${frappe.utils.escape_html(__("No Data"))}</td></tr>`
			);
			return;
		}

		const esc = frappe.utils.escape_html;
		const body = this.rows
			.map((row, idx) => {
				const editable = (field) =>
					`<input type="text" class="form-control input-sm cell-input" data-idx="${idx}" data-field="${field}" value="${esc(row[field] == null ? "" : row[field])}">`;

				return `<tr>
					<td>${idx + 1}</td>
					<td class="ellipsis" title="${esc(row.item_name || "")}">${esc(row.item_name || "")}</td>
					<td>${esc(row.custom_material || "")}</td>
					<td>${esc(row.custom_sf_code || "")}</td>
					<td>${esc(row.custom_drawing_no || "")}</td>
					<td>${editable("custom_revision")}</td>
					<td>${editable("custom_development_size_a")}</td>
					<td>${editable("custom_development_size_b")}</td>
					<td>${editable("custom_t")}</td>
				</tr>`;
			})
			.join("");

		this.$tbody.html(body);
		this.$tbody.find(".cell-input").on("change", (e) => {
			const $el = $(e.currentTarget);
			const idx = parseInt($el.data("idx"), 10);
			const field = $el.data("field");
			this.rows[idx][field] = $el.val();
			this.dirty.add(idx);
			this.$save_btn.prop("disabled", this.dirty.size === 0);
		});
	}

	save() {
		if (!this.dirty.size) return;

		const payload = Array.from(this.dirty).map((idx) => {
			const row = this.rows[idx];
			const out = { item_code: row.item_code };
			REVISION_EDITABLE.forEach((f) => (out[f] = row[f]));
			return out;
		});

		frappe.dom.freeze(__("Saving…"));
		rpc("save_revision_changes", { rows: payload })
			.then((res) => {
				const saved = (res && res.saved) || [];
				const errors = (res && res.errors) || [];

				if (saved.length) {
					frappe.show_alert({ message: __("Saved {0} item(s).", [saved.length]), indicator: "green" });
				}
				if (errors.length) {
					const msg = errors.map((e) => `${e.item_code}: ${e.error}`).join("<br>");
					frappe.msgprint({ title: __("Some rows failed"), message: msg, indicator: "red" });
				}

				this.dirty = new Set();
				this.$save_btn.prop("disabled", true);
				this.search();
			})
			.catch((err) => {
				frappe.show_alert({ message: err.message || __("Save failed"), indicator: "red" });
			})
			.finally(() => frappe.dom.unfreeze());
	}
};

frappe.pages["search-tools"].on_page_load = function (wrapper) {
	new bartakke_erp.pages.SearchToolsPage(wrapper).init();
};
