const QSO_METHODS = {
	search: "frappe.desk.search.search_link",
	itemDefaults: "shayona.shayona.page.quick_sales_order.quick_sales_order.get_item_defaults",
	create: "shayona.shayona.page.quick_sales_order.quick_sales_order.create_sales_order",
};

const qsoState = {
	items: [],
	editingIndex: null,
	currency: "INR",
	selectedCustomer: "",
	selectedItem: "",
	selectedItemName: "",
	itemRateReady: false,
	itemDefaultsRequestId: 0,
};

function qsoGet(id) {
	return document.getElementById(id);
}

function qsoNumber(value) {
	const number = Number(value);
	return Number.isFinite(number) ? number : 0;
}

function qsoFormatNumber(value) {
	return qsoNumber(value).toLocaleString(undefined, {
		maximumFractionDigits: 3,
	});
}

function qsoFormatCurrency(value) {
	try {
		return new Intl.NumberFormat(undefined, {
			style: "currency",
			currency: qsoState.currency || "INR",
			minimumFractionDigits: 2,
		}).format(qsoNumber(value));
	} catch (error) {
		return `${qsoState.currency || "INR"} ${qsoNumber(value).toFixed(2)}`;
	}
}

function qsoCurrencySymbol() {
	const formatted = qsoFormatCurrency(0);
	return formatted.replace(/[\d\s.,\u00a0]/g, "").trim() || qsoState.currency;
}

function qsoSetAlert(message, type = "success") {
	const alert = qsoGet("qso-alert");
	alert.textContent = message;
	alert.className = `qso-alert${type === "error" ? " qso-alert-error" : ""}`;
	alert.hidden = false;
	alert.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function qsoHideAlert() {
	qsoGet("qso-alert").hidden = true;
}

function qsoErrorMessage(error, fallback = __("Something went wrong.")) {
	const serverMessages = error?._server_messages || error?.responseJSON?._server_messages;

	if (serverMessages) {
		try {
			const messages = JSON.parse(serverMessages);
			const first = messages?.[0] ? JSON.parse(messages[0]) : null;
			return typeof first === "string" ? first : first?.message || fallback;
		} catch (parseError) {
			// Fall through to the normal response message.
		}
	}

	return error?.message || error?.responseJSON?.exception || fallback;
}

async function qsoCall(method, args = {}) {
	const response = await frappe.call({ method, args });
	return response.message;
}

function qsoSetButtonBusy(button, isBusy, busyLabel) {
	if (!button.dataset.normalLabel) {
		button.dataset.normalLabel = button.querySelector("span")?.textContent || button.textContent;
	}

	button.disabled = isBusy;
	const label = button.querySelector("span");
	if (label) {
		label.textContent = isBusy ? busyLabel : button.dataset.normalLabel;
	}
}

function qsoDebounce(callback, delay = 250) {
	let timer;
	return (...args) => {
		window.clearTimeout(timer);
		timer = window.setTimeout(() => callback(...args), delay);
	};
}

function qsoCreateAutocomplete({
	inputId,
	resultsId,
	doctype,
	referenceDoctype,
	linkFieldname,
	getQuery,
	getFilters,
	onSelect,
}) {
	const input = qsoGet(inputId);
	const results = qsoGet(resultsId);
	let requestId = 0;
	let selectedValue = "";

	function close() {
		results.hidden = true;
		input.setAttribute("aria-expanded", "false");
	}

	function render(options) {
		results.replaceChildren();

		if (!options.length) {
			const empty = document.createElement("div");
			empty.className = "qso-results-message";
			empty.textContent = __("No results found");
			results.appendChild(empty);
		} else {
			options.forEach((option) => {
				const button = document.createElement("button");
				button.type = "button";
				button.className = "qso-result-option";
				button.setAttribute("role", "option");

				const title = document.createElement("strong");
				title.textContent = option.label || option.value;
				button.appendChild(title);

				const detailText = [
					option.value !== (option.label || option.value) ? option.value : "",
					option.description || "",
				].filter(Boolean).join(" · ");

				if (detailText) {
					const detail = document.createElement("small");
					detail.textContent = detailText;
					button.appendChild(detail);
				}

				button.addEventListener("mousedown", (event) => {
					event.preventDefault();
					selectedValue = option.value;
					input.value = option.value;
					close();
					onSelect(option);
				});
				results.appendChild(button);
			});
		}

		results.hidden = false;
		input.setAttribute("aria-expanded", "true");
	}

	async function search() {
		const currentRequest = ++requestId;
		results.replaceChildren();
		const loading = document.createElement("div");
		loading.className = "qso-results-message";
		loading.textContent = __("Searching...");
		results.appendChild(loading);
		results.hidden = false;
		input.setAttribute("aria-expanded", "true");

		try {
			const options = await qsoCall(QSO_METHODS.search, {
				doctype,
				txt: input.value.trim(),
				query: getQuery?.() || "",
				filters: getFilters?.() || {},
				page_length: 10,
				reference_doctype: referenceDoctype,
				link_fieldname: linkFieldname,
			});

			if (currentRequest === requestId) {
				render(options || []);
			}
		} catch (error) {
			if (currentRequest === requestId) {
				close();
				qsoSetAlert(qsoErrorMessage(error, __("Unable to search.")), "error");
			}
		}
	}

	const debouncedSearch = qsoDebounce(search);
	input.addEventListener("focus", search);
	input.addEventListener("input", () => {
		if (input.value.trim() !== selectedValue) {
			selectedValue = "";
			onSelect(null);
		}
		debouncedSearch();
	});
	input.addEventListener("blur", () => window.setTimeout(close, 120));
	input.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			close();
		}
	});

	return {
		clear() {
			selectedValue = "";
			input.value = "";
			close();
		},
		setValue(value) {
			selectedValue = value || "";
			input.value = value || "";
			close();
		},
	};
}

function qsoGetOrderValues() {
	return {
		customer: qsoState.selectedCustomer || qsoGet("qso-customer").value.trim(),
		transactionDate: qsoGet("qso-order-date").value,
	};
}

async function qsoLoadItemDefaults() {
	const { customer, transactionDate } = qsoGetOrderValues();
	const itemCode = qsoState.selectedItem || qsoGet("qso-item-code").value.trim();
	const qty = qsoNumber(qsoGet("qso-qty").value);

	if (!customer || !transactionDate || !itemCode || qty <= 0) {
		return null;
	}

	const requestId = ++qsoState.itemDefaultsRequestId;
	const defaults = await qsoCall(QSO_METHODS.itemDefaults, {
		customer,
		transaction_date: transactionDate,
		item_code: itemCode,
		qty,
	});

	if (requestId !== qsoState.itemDefaultsRequestId) {
		return null;
	}

	qsoState.selectedItem = defaults.item_code;
	qsoState.selectedItemName = defaults.item_name || "";
	qsoState.currency = defaults.currency || qsoState.currency;
	qsoState.itemRateReady = true;
	qsoGet("qso-item-code").value = defaults.item_code;
	qsoGet("qso-selected-item-name").textContent = defaults.item_name || "";
	qsoGet("qso-rate").value = qsoNumber(defaults.rate);
	qsoGet("qso-rate-currency").textContent = qsoCurrencySymbol();
	qsoRenderSummary();
	return defaults;
}

function qsoResetItemEntry() {
	qsoState.editingIndex = null;
	qsoState.selectedItem = "";
	qsoState.selectedItemName = "";
	qsoState.itemRateReady = false;
	qsoState.itemDefaultsRequestId += 1;
	qsoItemAutocomplete.clear();
	qsoGet("qso-selected-item-name").textContent = "";
	qsoGet("qso-qty").value = 1;
	qsoGet("qso-rate").value = 0;
	qsoGet("qso-add-item").querySelector("span").textContent = __("Add Item");
}

function qsoRenderItems() {
	const list = qsoGet("qso-items-list");
	const empty = qsoGet("qso-items-empty");
	const clear = qsoGet("qso-clear-items");
	list.replaceChildren();

	if (!qsoState.items.length) {
		list.hidden = true;
		empty.hidden = false;
		clear.hidden = true;
		qsoGet("qso-item-count-badge").textContent = `0 ${__("Items")}`;
		qsoRenderSummary();
		return;
	}

	const header = document.createElement("div");
	header.className = "qso-item-row qso-item-head";
	["#", __("Item Code"), __("Item Name"), __("Qty"), __("Rate"), __("Amount"), __("Actions")]
		.forEach((label, index) => {
			const cell = document.createElement("div");
			cell.textContent = label;
			if ([3, 4, 5].includes(index)) cell.className = "qso-number";
			header.appendChild(cell);
		});
	list.appendChild(header);

	qsoState.items.forEach((item, index) => {
		const row = document.createElement("div");
		row.className = "qso-item-row";

		const cells = [
			{ className: "qso-index", text: index + 1 },
			{ className: "qso-item-code", text: item.item_code },
			{ className: "qso-item-name", text: item.item_name || "—" },
			{ className: "qso-item-qty qso-number", text: qsoFormatNumber(item.qty) },
			{ className: "qso-item-rate qso-number", text: qsoFormatCurrency(item.rate) },
			{ className: "qso-item-amount qso-number", text: qsoFormatCurrency(item.qty * item.rate) },
		];

		cells.forEach((definition) => {
			const cell = document.createElement("div");
			cell.className = definition.className;
			cell.textContent = definition.text;
			row.appendChild(cell);
		});

		const actions = document.createElement("div");
		actions.className = "qso-row-actions";
		actions.appendChild(qsoActionButton("edit", index, __("Edit item")));
		actions.appendChild(qsoActionButton("delete", index, __("Delete item")));
		row.appendChild(actions);
		list.appendChild(row);
	});

	list.hidden = false;
	empty.hidden = true;
	clear.hidden = false;
	qsoGet("qso-item-count-badge").textContent = `${qsoState.items.length} ${__("Items")}`;
	qsoRenderSummary();
}

function qsoActionButton(action, index, label) {
	const button = document.createElement("button");
	button.type = "button";
	button.className = "qso-icon-button";
	button.dataset.action = action;
	button.dataset.index = index;
	button.setAttribute("aria-label", label);
	button.title = label;
	button.innerHTML = action === "edit"
		? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg>'
		: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v6M14 11v6"/></svg>';
	return button;
}

function qsoRenderSummary() {
	const totalQty = qsoState.items.reduce((total, item) => total + qsoNumber(item.qty), 0);
	const subtotal = qsoState.items.reduce(
		(total, item) => total + qsoNumber(item.qty) * qsoNumber(item.rate),
		0
	);

	qsoGet("qso-total-items").textContent = qsoState.items.length;
	qsoGet("qso-total-qty").textContent = qsoFormatNumber(totalQty);
	qsoGet("qso-subtotal").textContent = qsoFormatCurrency(subtotal);
	qsoGet("qso-grand-total").textContent = qsoFormatCurrency(subtotal);
	qsoGet("qso-rate-currency").textContent = qsoCurrencySymbol();
}

async function qsoAddOrUpdateItem() {
	qsoHideAlert();
	const { customer, transactionDate } = qsoGetOrderValues();
	const itemCode = qsoState.selectedItem || qsoGet("qso-item-code").value.trim();
	const qty = qsoNumber(qsoGet("qso-qty").value);
	const rate = qsoNumber(qsoGet("qso-rate").value);

	if (!customer) {
		qsoSetAlert(__("Please select a Customer first."), "error");
		qsoGet("qso-customer").focus();
		return;
	}
	if (!transactionDate) {
		qsoSetAlert(__("Please select an Order Date."), "error");
		return;
	}
	if (!itemCode) {
		qsoSetAlert(__("Please select an Item."), "error");
		qsoGet("qso-item-code").focus();
		return;
	}
	if (qty <= 0) {
		qsoSetAlert(__("Quantity must be greater than zero."), "error");
		return;
	}
	if (rate < 0) {
		qsoSetAlert(__("Rate cannot be negative."), "error");
		return;
	}

	const button = qsoGet("qso-add-item");
	qsoSetButtonBusy(button, true, __("Adding..."));

	try {
		let defaults = null;
		if (!qsoState.itemRateReady) {
			defaults = await qsoLoadItemDefaults();
		}

		const item = {
			item_code: defaults?.item_code || itemCode,
			item_name: defaults?.item_name || qsoState.selectedItemName,
			qty,
			rate: defaults ? qsoNumber(defaults.rate) : qsoNumber(qsoGet("qso-rate").value),
		};

		if (qsoState.editingIndex === null) {
			qsoState.items.push(item);
		} else {
			qsoState.items[qsoState.editingIndex] = item;
		}

		qsoResetItemEntry();
		qsoRenderItems();
		qsoGet("qso-item-code").focus();
	} catch (error) {
		qsoSetAlert(qsoErrorMessage(error, __("Unable to add this item.")), "error");
	} finally {
		qsoSetButtonBusy(button, false, __("Adding..."));
	}
}

function qsoEditItem(index) {
	const item = qsoState.items[index];
	if (!item) return;

	qsoState.editingIndex = index;
	qsoState.selectedItem = item.item_code;
	qsoState.selectedItemName = item.item_name || "";
	qsoState.itemRateReady = true;
	qsoItemAutocomplete.setValue(item.item_code);
	qsoGet("qso-selected-item-name").textContent = item.item_name || "";
	qsoGet("qso-qty").value = item.qty;
	qsoGet("qso-rate").value = item.rate;
	qsoGet("qso-add-item").querySelector("span").textContent = __("Update Item");
	qsoGet("qso-item-code").scrollIntoView({ behavior: "smooth", block: "center" });
}

function qsoDeleteItem(index) {
	qsoState.items.splice(index, 1);
	if (qsoState.editingIndex === index) qsoResetItemEntry();
	qsoRenderItems();
}

async function qsoSaveOrder() {
	qsoHideAlert();
	const { customer, transactionDate } = qsoGetOrderValues();

	if (!customer) {
		qsoSetAlert(__("Please select a Customer."), "error");
		return;
	}
	if (!transactionDate) {
		qsoSetAlert(__("Please select an Order Date."), "error");
		return;
	}
	if (!qsoState.items.length) {
		qsoSetAlert(__("Please add at least one item."), "error");
		return;
	}

	const button = qsoGet("qso-save-order");
	qsoSetButtonBusy(button, true, __("Saving..."));

	try {
		const result = await qsoCall(QSO_METHODS.create, {
			customer,
			transaction_date: transactionDate,
			items: qsoState.items.map((item) => ({
				item_code: item.item_code,
				qty: item.qty,
				rate: item.rate,
			})),
		});

		qsoSetAlert(__("Sales Order {0} created successfully.", [result.name]));
		window.setTimeout(() => {
			window.location.assign(`/app/sales-order/${encodeURIComponent(result.name)}`);
		}, 550);
	} catch (error) {
		qsoSetAlert(qsoErrorMessage(error, __("Unable to save the Sales Order.")), "error");
		qsoSetButtonBusy(button, false, __("Saving..."));
	}
}

let qsoItemAutocomplete;

frappe.ready(() => {
	qsoCreateAutocomplete({
		inputId: "qso-customer",
		resultsId: "qso-customer-results",
		doctype: "Customer",
		referenceDoctype: "Sales Order",
		linkFieldname: "customer",
		onSelect: (option) => {
			qsoState.selectedCustomer = option?.value || "";
		},
	});

	qsoItemAutocomplete = qsoCreateAutocomplete({
		inputId: "qso-item-code",
		resultsId: "qso-item-results",
		doctype: "Item",
		referenceDoctype: "Sales Order Item",
		linkFieldname: "item_code",
		getQuery: () => "erpnext.controllers.queries.item_query",
		getFilters: () => ({
			is_sales_item: 1,
			has_variants: 0,
			customer: qsoState.selectedCustomer || qsoGet("qso-customer").value.trim(),
		}),
		onSelect: async (option) => {
			qsoState.selectedItem = option?.value || "";
			qsoState.selectedItemName = option?.label && option.label !== option.value
				? option.label
				: "";
			qsoState.itemRateReady = false;
			qsoGet("qso-selected-item-name").textContent = qsoState.selectedItemName;
			if (!option) return;

			// Every fresh item selection starts with quantity 1.
			qsoGet("qso-qty").value = 1;
			qsoGet("qso-rate").value = 0;
			try {
				await qsoLoadItemDefaults();
			} catch (error) {
				qsoSetAlert(qsoErrorMessage(error, __("Unable to load the item rate.")), "error");
			}
		},
	});

	qsoGet("qso-rate").addEventListener("input", () => {
		qsoState.itemRateReady = true;
	});

	qsoGet("qso-add-item").addEventListener("click", qsoAddOrUpdateItem);
	qsoGet("qso-save-order").addEventListener("click", qsoSaveOrder);
	qsoGet("qso-clear-items").addEventListener("click", () => {
		qsoState.items = [];
		qsoResetItemEntry();
		qsoRenderItems();
	});

	qsoGet("qso-items-list").addEventListener("click", (event) => {
		const button = event.target.closest("[data-action]");
		if (!button) return;
		const index = Number(button.dataset.index);
		if (button.dataset.action === "edit") qsoEditItem(index);
		if (button.dataset.action === "delete") qsoDeleteItem(index);
	});

	qsoRenderItems();
});
