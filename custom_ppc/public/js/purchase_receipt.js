// Custom PPC - package popup on Purchase Receipt
// Items with "Track by Package": ask Tag ID / No. of packages / Qty per package,
// create one Batch per package and split the row into one row per package.

frappe.provide("custom_ppc");

frappe.ui.form.on("Purchase Receipt", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;
        frm.add_custom_button(__("Enter Packages"), () => custom_ppc.pick_row(frm));
    },
});

frappe.ui.form.on("Purchase Receipt Item", {
    item_code(frm, cdt, cdn) {
        // let ERPNext fill rate / uom / warehouse first
        setTimeout(() => custom_ppc.maybe_open(frm, cdn), 800);
    },
});

custom_ppc.package_info = function (item_code) {
    return frappe
        .call({ method: "custom_ppc.api.package_info", args: { item_code } })
        .then((r) => r.message || null);
};

custom_ppc.maybe_open = async function (frm, cdn) {
    const row = locals["Purchase Receipt Item"][cdn];
    if (!row || !row.item_code || row.batch_no) return;
    const info = await custom_ppc.package_info(row.item_code);
    if (!info) return;
    // packages are entered through our popup, not ERPNext's batch selector
    row.use_serial_batch_fields = 1;
    custom_ppc.open_dialog(frm, row, info);
};

// ERPNext opens its own "Add Batch Nos" selector when a batch item is picked;
// close it so only the package popup is shown.
custom_ppc.close_batch_selector = function (keep) {
    const titles = [__("Add Batch Nos"), __("Add Serial Nos"), __("Add Serial / Batch No"), __("Add Batch Nos")];
    (frappe.ui.open_dialogs || []).slice().forEach((dlg) => {
        if (dlg !== keep && titles.includes(dlg.title)) dlg.hide();
    });
};

// "Enter Packages" button: package rows without packages yet (e.g. receipts made by OCR)
custom_ppc.pick_row = async function (frm) {
    const pending = [];
    for (const row of frm.doc.items || []) {
        if (!row.item_code || row.batch_no) continue;
        const info = await custom_ppc.package_info(row.item_code);
        if (info) pending.push({ row, info });
    }
    if (!pending.length) {
        frappe.msgprint(__("No package rows without packages."));
        return;
    }
    if (pending.length === 1) return custom_ppc.open_dialog(frm, pending[0].row, pending[0].info);

    const d = new frappe.ui.Dialog({
        title: __("Which row?"),
        fields: [{
            fieldname: "row", fieldtype: "Select", label: __("Row"), reqd: 1,
            options: pending.map((p) => ({ value: p.row.name, label: `Row ${p.row.idx}: ${p.row.item_code} (${p.row.qty})` })),
        }],
        primary_action_label: __("Next"),
        primary_action(v) {
            d.hide();
            const p = pending.find((x) => x.row.name === v.row);
            custom_ppc.open_dialog(frm, p.row, p.info);
        },
    });
    d.show();
};

custom_ppc.open_dialog = function (frm, row, info) {
    const pkg = info.package_uom, unit = info.stock_uom;
    const d = new frappe.ui.Dialog({
        title: __("{0} for {1}", [pkg, row.item_code]),
        size: "large",
        fields: [
            { fieldtype: "HTML", fieldname: "info" },
            {
                fieldname: "lines", fieldtype: "Table", label: __("Packing list"),
                in_place_edit: true, reqd: 1, data: [],
                fields: [
                    { fieldname: "tag_id", fieldtype: "Data", label: __("Tag ID"), in_list_view: 1, reqd: 1, columns: 2 },
                    { fieldname: "packages", fieldtype: "Int", label: __("No. of Packages"), in_list_view: 1, reqd: 1, columns: 2,
                      onchange: () => update_totals() },
                    { fieldname: "package_uom", fieldtype: "Link", options: "UOM", label: __("Package Unit"), in_list_view: 1, reqd: 1, columns: 1,
                      default: pkg },
                    { fieldname: "qty", fieldtype: "Float", label: __("{0} per Package", [unit]), in_list_view: 1, reqd: 1, columns: 2,
                      onchange: () => update_totals() },
                    { fieldname: "total", fieldtype: "Float", label: __("Total {0}", [unit]), in_list_view: 1, read_only: 1, columns: 2 },
                ],
            },
        ],
        primary_action_label: __("Create {0}", [pkg]),
        primary_action: () => create(),
    });

    const grid_rows = () => d.fields_dict.lines.grid.get_data() || [];

    function update_totals() {
        let count = 0, total = 0;
        grid_rows().forEach((l) => {
            l.total = flt(l.packages) * flt(l.qty);
            count += cint(l.packages);
            total += l.total;
        });
        d.fields_dict.lines.grid.refresh();
        // qty 1 is just the default on a new row; only compare against a real qty (e.g. from OCR)
        const row_qty = flt(row.qty) > 1 ? flt(row.qty) : 0;
        const diff = row_qty ? total - row_qty : 0;
        d.fields_dict.info.$wrapper.html(`
            <div class="text-muted small" style="margin-bottom:8px">
                ${__("Row qty")}: <b>${row_qty || "-"}</b> &nbsp;|&nbsp;
                ${__("Packages")}: <b>${count}</b> &nbsp;|&nbsp;
                ${__("Total {0}", [unit])}: <b>${total}</b>
                ${diff ? `<span class="text-danger"> &nbsp;(${__("difference")} ${diff > 0 ? "+" : ""}${diff})</span>` : ""}
            </div>`);
    }

    async function create() {
        const lines = grid_rows()
            .filter((l) => l.tag_id || l.packages || l.qty)
            .map((l) => ({ tag_id: (l.tag_id || "").trim(), packages: cint(l.packages), qty: flt(l.qty),
                           package_uom: l.package_uom || pkg }));
        if (!lines.length || lines.some((l) => !l.tag_id || l.packages <= 0 || l.qty <= 0)) {
            frappe.msgprint(__("Fill Tag ID, No. of {0} and {1} per {0} on every line.", [pkg, unit]));
            return;
        }
        const r = await frappe.call({
            method: "custom_ppc.api.create_packages",
            args: { item_code: row.item_code, lines: JSON.stringify(lines),
                    purchase_receipt: frm.is_new() ? null : frm.doc.name },
            freeze: true,
            freeze_message: __("Creating {0}...", [pkg]),
        });
        if (!r.message || !r.message.length) return;
        custom_ppc.split_row(frm, row, r.message);
        d.hide();
        frappe.show_alert({ message: __("{0} {1} added", [r.message.length, pkg]), indicator: "green" });
    }

    d.fields_dict.lines.grid.add_new_row();
    (d.fields_dict.lines.grid.get_data() || []).forEach((l) => (l.package_uom = l.package_uom || pkg));
    update_totals();
    custom_ppc.close_batch_selector(d);
    d.show();
    // ERPNext's selector can open a moment later
    setTimeout(() => custom_ppc.close_batch_selector(d), 1500);
};

// Replace one row with one row per package, keeping rate, warehouse, uom etc.
custom_ppc.split_row = function (frm, row, packages) {
    const skip = ["name", "idx", "__islocal", "__unsaved", "docstatus", "batch_no",
        "serial_and_batch_bundle", "rejected_serial_and_batch_bundle"];
    const template = {};
    Object.keys(row).forEach((k) => { if (!skip.includes(k)) template[k] = row[k]; });
    const cf = flt(row.conversion_factor) || 1;

    const apply = (target, p) => Object.assign(target, template, {
        batch_no: p.batch_no, use_serial_batch_fields: 1,
        qty: p.qty, received_qty: p.qty, rejected_qty: 0,
        stock_qty: p.qty * cf, received_stock_qty: p.qty * cf,
    });

    apply(row, packages[0]);
    packages.slice(1).forEach((p) => apply(frm.add_child("items"), p));

    // keep the new rows directly under the original row
    const items = frm.doc.items;
    const extra = items.splice(items.length - (packages.length - 1), packages.length - 1);
    items.splice(row.idx, 0, ...extra);
    items.forEach((it, i) => (it.idx = i + 1));

    frm.refresh_field("items");
    if (frm.cscript && frm.cscript.calculate_taxes_and_totals) frm.cscript.calculate_taxes_and_totals();
    frm.dirty();
};
