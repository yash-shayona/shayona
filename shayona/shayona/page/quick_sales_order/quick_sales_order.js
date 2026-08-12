frappe.provide("shayona.quick_sales_order");

frappe.pages["quick-sales-order"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Quick Sales Order"),
		single_column: true,
	});

	if (!frappe.model.can_create("Sales Order")) {
		page.body.html(`
			<div class="frappe-card p-6 text-center text-muted">
				${__("You do not have permission to create a Sales Order.")}
			</div>
		`);
		return;
	}

	frappe.model.with_doctype("Sales Order Item", () => {
		wrapper.quick_sales_order = new shayona.quick_sales_order.QuickSalesOrder(page);
	});
};

shayona.quick_sales_order.QuickSalesOrder = class QuickSalesOrder {
	constructor(page) {
		this.page = page;
		this.items = [];
		this.custom_rate_request_id = 0;
		this.make_form();
		this.page.set_primary_action(
			__("Save Sales Order"),
			() => this.save(),
			"save",
			__("Saving...")
		);
	}

	make_form() {
		const quick_sales_order = this;
		this.form_wrapper = $('<div class="quick-sales-order-form"></div>').appendTo(
			this.page.body
		);

		this.form = new frappe.ui.FieldGroup({
			body: this.form_wrapper,
			fields: [
				{
					fieldtype: "Section Break",
					label: __("Order Details"),
				},
				{
					fieldname: "customer",
					fieldtype: "Link",
					label: __("Customer"),
					options: "Customer",
					reqd: 1,
					change: () => this.refresh_automatic_rates(),
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldname: "transaction_date",
					fieldtype: "Date",
					label: __("Order Date"),
					default: "Today",
					reqd: 1,
					change: () => this.refresh_automatic_rates(),
				},
				{
					fieldtype: "Section Break",
					label: __("Items"),
				},
				{
					fieldname: "use_custom_item_entry",
					fieldtype: "Check",
					label: __("Use Custom Item Entry"),
					description: __("Uncheck to use the Standard Grid."),
					default: 1,
					change: () => this.toggle_item_entry_mode(),
				},
				{
					fieldname: "custom_item_entry",
					fieldtype: "HTML",
				},
				{
					fieldname: "items",
					fieldtype: "Table",
					label: "Items",
					options: "Sales Order Item",
					in_place_edit: false,
					data: this.items,
					get_data: () => this.items,
					fields: [
						{
							fieldname: "item_code",
							fieldtype: "Link",
							label: __("Item Code"),
							options: "Item",
							reqd: 1,
							in_list_view: 1,
							columns: 5,
							get_query: () => this.get_item_query(),
							onchange: function () {
								return quick_sales_order.handle_item_change(this.grid_row);
							},
						},
						{
							fieldname: "item_name",
							fieldtype: "Data",
							label: __("Item Name"),
							read_only: 1,
							in_list_view: 0,
						},
						{
							fieldname: "qty",
							fieldtype: "Float",
							label: __("Quantity"),
							reqd: 1,
							in_list_view: 1,
							columns: 2,
							onchange: function () {
								return quick_sales_order.handle_quantity_change(this.grid_row);
							},
						},
						{
							fieldname: "rate",
							fieldtype: "Currency",
							label: __("Rate"),
							in_list_view: 1,
							columns: 3,
							onchange: function () {
								quick_sales_order.handle_rate_change(this.grid_row);
							},
						},
					],
				},
			],
		});

		this.form.make();
		this.items_field = this.form.get_field("items");
		this.custom_item_field = this.form.get_field("custom_item_entry");
		this.make_custom_item_entry();
		this.toggle_item_entry_mode();
		this.setup_grid_form_dismiss();
	}

	setup_grid_form_dismiss() {
		$(document)
			.off("click.quick_sales_order_grid_form", "#freeze.grid-form")
			.on("click.quick_sales_order_grid_form", "#freeze.grid-form", () => {
				const open_row = frappe.ui.form.get_open_grid_form();
				if (!open_row || open_row.grid !== this.items_field.grid) {
					return;
				}

				open_row.toggle_view(false);
				return false;
			});
	}

	get_item_query() {
		return {
			query: "erpnext.controllers.queries.item_query",
			filters: {
				is_sales_item: 1,
				has_variants: 0,
				customer: this.form.get_value("customer") || "",
			},
		};
	}

	make_custom_item_entry() {
		const quick_sales_order = this;
		this.custom_item_field.$wrapper.empty();
		this.custom_item_wrapper = $(
			`<div class="quick-custom-item-entry">
				<div class="quick-custom-item-fields"></div>
				<div class="quick-custom-item-actions"></div>
				<div class="quick-custom-item-list"></div>
			</div>`
		).appendTo(this.custom_item_field.$wrapper);

		this.custom_item_form = new frappe.ui.FieldGroup({
			body: this.custom_item_wrapper.find(".quick-custom-item-fields"),
			fields: [
				{
					fieldtype: "Section Break",
				},
				{
					fieldname: "item_code",
					fieldtype: "Link",
					label: __("Item Code"),
					options: "Item",
					reqd: 1,
					get_query: () => this.get_item_query(),
					change: () => this.handle_custom_item_change(),
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldname: "qty",
					fieldtype: "Float",
					label: __("Quantity"),
					default: 1,
					reqd: 1,
					change: () => this.handle_custom_quantity_change(),
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldname: "rate",
					fieldtype: "Currency",
					label: __("Rate"),
					change: () => {
						if (!this.resetting_custom_item) {
							this.custom_rate_request_id += 1;
						}
					},
				},
			],
		});
		this.custom_item_form.make();

		this.custom_add_button = $(
			'<button type="button" class="btn btn-primary btn-sm"></button>'
		)
			.append(frappe.utils.icon("add", "sm"), $("<span></span>").text(__("Add Item")))
			.appendTo(this.custom_item_wrapper.find(".quick-custom-item-actions"))
			.on("click", async function () {
				const button = $(this);
				button.prop("disabled", true);
				try {
					await quick_sales_order.add_custom_item();
				} finally {
					button.prop("disabled", false);
				}
			});

		this.render_custom_item_rows();
	}

	toggle_item_entry_mode() {
		if (!this.items_field || !this.custom_item_field) {
			return;
		}

		const use_custom_entry = cint(this.form.get_value("use_custom_item_entry"));
		this.custom_item_field.$wrapper.toggle(Boolean(use_custom_entry));
		this.items_field.$wrapper.toggle(!use_custom_entry);

		if (use_custom_entry) {
			this.render_custom_item_rows();
		}
	}

	get_header_values() {
		return {
			customer: this.form.get_value("customer"),
			transaction_date: this.form.get_value("transaction_date"),
		};
	}

	has_complete_header(values = this.get_header_values()) {
		return Boolean(values.customer && values.transaction_date);
	}

	async handle_custom_item_change() {
		if (this.resetting_custom_item) {
			return;
		}

		this.custom_rate_request_id += 1;
		this.custom_item_name = null;
		const item_code = this.custom_item_form.get_value("item_code");
		if (!item_code) {
			await this.set_custom_rate(null);
			return;
		}

		if (!flt(this.custom_item_form.get_value("qty"))) {
			await this.custom_item_form.set_value("qty", 1);
		}

		if (!this.has_complete_header()) {
			frappe.show_alert({
				message: __("Select Customer and Order Date to fetch the item rate."),
				indicator: "orange",
			});
			return;
		}

		await this.fetch_custom_item_rate();
	}

	async handle_custom_quantity_change() {
		if (
			this.resetting_custom_item ||
			!this.custom_item_form.get_value("item_code") ||
			!this.has_complete_header()
		) {
			return;
		}

		await this.fetch_custom_item_rate();
	}

	async set_custom_rate(rate) {
		await this.custom_item_form.set_value("rate", rate);
	}

	async fetch_custom_item_rate() {
		const item_code = this.custom_item_form.get_value("item_code");
		if (!item_code || !this.has_complete_header()) {
			return;
		}

		const request_id = ++this.custom_rate_request_id;
		const response = await frappe.call({
			method:
				"shayona.shayona.page.quick_sales_order.quick_sales_order.get_item_defaults",
			args: {
				...this.get_header_values(),
				item_code,
				qty: this.custom_item_form.get_value("qty") || 1,
			},
		});

		if (request_id !== this.custom_rate_request_id || !response.message) {
			return;
		}

		this.currency = response.message.currency;
		this.custom_item_name = response.message.item_name;
		await this.set_custom_rate(response.message.rate);
	}

	async add_custom_item() {
		let values = this.custom_item_form.get_values();
		if (!values) {
			return;
		}

		if (!this.has_complete_header()) {
			frappe.throw(__("Please select Customer and Order Date."));
		}

		if (flt(values.qty) <= 0) {
			frappe.throw(__("Quantity must be greater than zero."));
		}

		if (values.rate === undefined) {
			await this.fetch_custom_item_rate();
			values = this.custom_item_form.get_values();
			if (!values) {
				return;
			}
		}

		this.items.push({
			item_code: values.item_code,
			item_name:
				this.custom_item_name || frappe.utils.get_link_title("Item", values.item_code),
			qty: flt(values.qty),
			rate: flt(this.custom_item_form.get_value("rate")),
		});
		this.items_field.grid.refresh();
		this.render_custom_item_rows();
		await this.reset_custom_item_entry();

		frappe.show_alert({
			message: __("Item added."),
			indicator: "green",
		});
	}

	async reset_custom_item_entry() {
		this.resetting_custom_item = true;
		this.custom_item_name = null;
		this.custom_rate_request_id += 1;
		try {
			await this.custom_item_form.set_values({
				item_code: "",
				qty: 1,
				rate: "",
			});
		} finally {
			this.resetting_custom_item = false;
		}
	}

	render_custom_item_rows() {
		if (!this.custom_item_wrapper || !this.items_field) {
			return;
		}

		const list = this.custom_item_wrapper.find(".quick-custom-item-list").empty();
		const rows = this.items_field.grid
			.get_data()
			.filter((row) => row.item_code || flt(row.qty) || flt(row.rate));
		if (!rows.length) {
			$("<div class=\"quick-custom-item-empty text-muted\"></div>")
				.text(__("No items added yet."))
				.appendTo(list);
			return;
		}

		const header = $('<div class="quick-custom-item-list-header"></div>').appendTo(list);
		[__("Item"), __("Quantity"), __("Rate"), ""].forEach((label) => {
			$("<div></div>").text(label).appendTo(header);
		});

		rows.forEach((row) => {
			const item_row = $('<div class="quick-custom-item-row"></div>').appendTo(list);
			const item_name =
				row.item_name || frappe.utils.get_link_title("Item", row.item_code);
			const item_label =
				row.item_code && item_name && item_name !== row.item_code
					? `${row.item_code}: ${item_name}`
					: row.item_code;
			$("<div class=\"quick-custom-item-code\"></div>")
				.toggleClass("text-danger", !row.item_code)
				.text(item_label || __("Item not selected"))
				.appendTo(item_row);
			$("<div class=\"quick-custom-item-qty\"></div>")
				.text(flt(row.qty))
				.appendTo(item_row);
			$("<div class=\"quick-custom-item-rate\"></div>")
				.text(format_currency(flt(row.rate), this.currency))
				.appendTo(item_row);
			$('<button type="button" class="btn btn-link btn-sm quick-custom-item-remove"></button>')
				.attr({ title: __("Remove Item"), "aria-label": __("Remove Item") })
				.html(frappe.utils.icon("delete", "sm"))
				.appendTo(item_row)
				.on("click", () => this.remove_custom_item(row));
		});
	}

	remove_custom_item(item_row) {
		const rows = this.items_field.grid.get_data();
		const index = rows.indexOf(item_row);
		if (index === -1) {
			return;
		}

		rows.splice(index, 1);
		rows.forEach((row, row_index) => {
			row.idx = row_index + 1;
		});
		this.items_field.grid.refresh();
		this.render_custom_item_rows();
	}

	async handle_item_change(grid_row) {
		const row = grid_row.doc;

		if (!row.item_code) {
			row.item_name = null;
			row.rate = null;
			grid_row.refresh();
			return;
		}

		if (!flt(row.qty)) {
			row.qty = 1;
		}

		if (!this.has_complete_header()) {
			grid_row.refresh();
			frappe.show_alert({
				message: __("Select Customer and Order Date to fetch the item rate."),
				indicator: "orange",
			});
			return;
		}

		await this.fetch_automatic_rate(row, grid_row);
	}

	async handle_quantity_change(grid_row) {
		const row = grid_row.doc;

		if (row.item_code && this.has_complete_header()) {
			await this.fetch_automatic_rate(row, grid_row);
		}
	}

	handle_rate_change(grid_row) {
		// A user-entered rate must win over an older automatic-rate response.
		const row = grid_row.doc;
		row.__quick_rate_request_id = cint(row.__quick_rate_request_id) + 1;
	}

	async fetch_automatic_rate(row, grid_row = null) {
		const header = this.get_header_values();
		const request_id = cint(row.__quick_rate_request_id) + 1;
		row.__quick_rate_request_id = request_id;

		const response = await frappe.call({
			method:
				"shayona.shayona.page.quick_sales_order.quick_sales_order.get_item_defaults",
			args: {
				...header,
				item_code: row.item_code,
				qty: row.qty || 1,
			},
		});

		if (request_id !== row.__quick_rate_request_id || !response.message) {
			return;
		}

		row.item_name = response.message.item_name;
		row.rate = response.message.rate;
		this.currency = response.message.currency;

		if (grid_row) {
			grid_row.refresh();
		} else {
			this.items_field.grid.refresh();
		}
		this.render_custom_item_rows();
	}

	async refresh_automatic_rates() {
		if (!this.items_field || !this.has_complete_header()) {
			return;
		}

		const automatic_rate_rows = this.items.filter((row) => row.item_code);
		const requests = automatic_rate_rows.map((row) => this.fetch_automatic_rate(row));
		if (this.custom_item_form?.get_value("item_code")) {
			requests.push(this.fetch_custom_item_rate());
		}

		await Promise.all(requests);
	}

	get_items_for_save() {
		const rows = this.items_field.grid
			.get_data()
			.filter((row) => row.item_code || flt(row.qty) || flt(row.rate));

		if (!rows.length) {
			frappe.throw(__("Please add at least one item."));
		}

		return rows.map((row, index) => {
			if (!row.item_code) {
				frappe.throw(__("Row {0}: Item Code is required.", [index + 1]));
			}

			if (flt(row.qty) <= 0) {
				frappe.throw(__("Row {0}: Quantity must be greater than zero.", [index + 1]));
			}

			const item = {
				item_code: row.item_code,
				qty: flt(row.qty),
				rate: flt(row.rate),
			};

			return item;
		});
	}

	async save() {
		const values = this.form.get_values();
		if (!values) {
			return;
		}

		const response = await frappe.call({
			method:
				"shayona.shayona.page.quick_sales_order.quick_sales_order.create_sales_order",
			type: "POST",
			freeze: true,
			freeze_message: __("Creating Sales Order..."),
			args: {
				customer: values.customer,
				transaction_date: values.transaction_date,
				items: this.get_items_for_save(),
			},
		});

		if (response.message?.name) {
			frappe.show_alert({
				message: __("Sales Order {0} created.", [response.message.name]),
				indicator: "green",
			});
			frappe.set_route("Form", "Sales Order", response.message.name);
		}
	}
};
