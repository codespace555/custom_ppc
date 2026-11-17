// Custom PPC - package picker on Stock Entry
// Works for every Stock Entry row that takes stock out of a warehouse (s_warehouse):
// Material Transfer, Material Transfer for Manufacture, Material Issue,
// Send to Subcontractor, Manufacture (raw material rows) ...
// Full packages default to their balance; a part package takes a typed qty.

frappe.provide("custom_ppc");

// Switch: Custom PPC Settings > "Use Custom PPC package picker on Stock Entry".
// Off (default) = ERPNext's standard Add Batch Nos dialog is used.
custom_ppc.picker_enabled = function () {
    if (!custom_ppc._picker_enabled) {
        custom_ppc._picker_enabled = frappe.db
            .get_single_value("Custom PPC Settings", "enable_stock_entry_picker")
            .then((v) => !!cint(v))
            .catch(() => false);
    }
    return custom_ppc._picker_enabled;
};

frappe.ui.form.on("Stock Entry", {
    onload() {
        custom_ppc._picker_enabled = null; // re-read the setting for each form
    },
    async refresh(frm) {
        if (frm.doc.docstatus !== 0 || !(await custom_ppc.picker_enabled())) return;
        frm.add_custom_button(__("Pick Packages"), () => custom_ppc.se_pick_row(frm));
    },
});

frappe.ui.form.on("Stock Entry Detail", {
    async item_code(frm, cdt, cdn) {
        if (!(await custom_ppc.picker_enabled())) return;
        setTimeout(() => custom_ppc.se_maybe_open(frm, cdn), 800);
    },
});

custom_ppc.se_info = function (item_code) {
    return frappe
        .call({ method: "custom_ppc.api.package_info", args: { item_code } })
        .then((r) => r.message || null);
};

custom_ppc.se_close_batch_selector = function (keep) {
    const titles = [__("Add Batch Nos"), __("Add Serial Nos"), __("Add Serial / Batch No")];
    (frappe.ui.open_dialogs || []).slice().forEach((dlg) => {
        if (dlg !== keep && titles.includes(dlg.title)) dlg.hide();
    });
};

custom_ppc.se_maybe_open = async function (frm, cdn) {
    const row = locals["Stock Entry Detail"][cdn];
    if (!row || !row.item_code || row.batch_no || !row.s_warehouse) return;
    const info = await custom_ppc.se_info(row.item_code);
    if (!info) return;
    row.use_serial_batch_fields = 1;
    custom_ppc.se_open_picker(frm, row, info);
};

// "Pick Packages" button: rows of package items with a source warehouse and no package yet
custom_ppc.se_pick_row = async function (frm) {
    const pending = [];
    for (const row of frm.doc.items || []) {
        if (!row.item_code || row.batch_no || !row.s_warehouse) continue;
        const info = await custom_ppc.se_info(row.item_code);
        if (info) pending.push({ row, info });
    }
    if (!pending.length) {
        frappe.msgprint(__("No rows to pick. A row needs an item tracked by package, a source warehouse and no package yet."));
        return;
    }
    if (pending.length === 1) return custom_ppc.se_open_picker(frm, pending[0].row, pending[0].info);

    const d = new frappe.ui.Dialog({
        title: __("Which row?"),
        fields: [{
            fieldname: "row", fieldtype: "Select", label: __("Row"), reqd: 1,
            options: pending.map((p) => ({ value: p.row.name,
                label: `Row ${p.row.idx}: ${p.row.item_code} (${p.row.qty}) from ${p.row.s_warehouse}` })),
        }],
        primary_action_label: __("Next"),
        primary_action(v) {
            d.hide();
            const p = pending.find((x) => x.row.name === v.row);
            custom_ppc.se_open_picker(frm, p.row, p.info);
        },
    });
    d.show();
};

custom_ppc.se_open_picker = async function (frm, row, info) {
    const r = await frappe.call({
        method: "custom_ppc.api.get_packages",
        args: { item_code: row.item_code, warehouse: row.s_warehouse },
    });
    const all = (r.message || []).map((p) => Object.assign(p, {
        pick: 0, issue_qty: 0, _was: 0,
        package: `${p.package_no || ""} ${p.package_uom || ""}`.trim(),
    }));
    if (!all.length) {
        frappe.msgprint(__("No packages of {0} in {1}.", [row.item_code, row.s_warehouse]));
        return;
    }
    const unit = info.stock_uom;
    const cf = flt(row.conversion_factor) || 1;
    // qty 1 is just the default on a new row; only use a real required qty (e.g. from a Work Order)
    const required = flt(row.qty) > 1 ? flt(row.qty) * cf : 0;

    const d = new frappe.ui.Dialog({
        title: __("Pick packages: {0}", [row.item_code]),
        size: "extra-large",
        fields: [
            { fieldtype: "HTML", fieldname: "info" },
            { fieldtype: "Data", fieldname: "tag_filter", label: __("Filter by Tag ID"),
              onchange: () => apply_filter() },
            {
                fieldname: "packages", fieldtype: "Table", label: __("Packages in {0}", [row.s_warehouse]),
                cannot_add_rows: true, cannot_delete_rows: true, in_place_edit: true, data: all,
                fields: [
                    { fieldname: "pick", fieldtype: "Check", label: __("Pick"), in_list_view: 1, columns: 1,
                      onchange: () => update() },
                    { fieldname: "tag_id", fieldtype: "Data", label: __("Tag ID"), in_list_view: 1, read_only: 1, columns: 2 },
                    { fieldname: "package", fieldtype: "Data", label: __("Package"), in_list_view: 1, read_only: 1, columns: 1 },
                    { fieldname: "qty_per_package", fieldtype: "Float", label: __("Size ({0})", [unit]), in_list_view: 1, read_only: 1, columns: 1 },
                    { fieldname: "balance", fieldtype: "Float", label: __("Balance ({0})", [unit]), in_list_view: 1, read_only: 1, columns: 2 },
                    { fieldname: "issue_qty", fieldtype: "Float", label: __("Issue Qty ({0})", [unit]), in_list_view: 1, columns: 2,
                      onchange: () => update() },
                    { fieldname: "batch_no", fieldtype: "Data", label: __("Batch"), read_only: 1 },
                ],
            },
        ],
        primary_action_label: __("Add to Entry"),
        primary_action: () => submit(),
        secondary_action_label: required ? __("Fill {0} {1}", [required, unit]) : null,
        secondary_action: required ? () => fill_required() : null,
    });

    const grid = () => d.fields_dict.packages.grid;

    function apply_filter() {
        const t = (d.get_value("tag_filter") || "").trim().toLowerCase();
        grid().df.data = t ? all.filter((p) => (p.tag_id || "").toLowerCase().includes(t)) : all;
        grid().refresh();
    }

    function update() {
        let count = 0, total = 0;
        all.forEach((p) => {
            if (p.pick && !p._was) { if (!flt(p.issue_qty)) p.issue_qty = p.balance; }
            else if (!p.pick && p._was) { p.issue_qty = 0; }
            else if (!p.pick && flt(p.issue_qty) > 0) { p.pick = 1; }
            p._was = p.pick ? 1 : 0;
            if (p.pick) { count += 1; total += flt(p.issue_qty); }
        });
        grid().refresh();
        const over = all.filter((p) => flt(p.issue_qty) > flt(p.balance) + 0.0001);
        const diff = required ? total - required : 0;
        d.fields_dict.info.$wrapper.html(`
            <div class="text-muted small" style="margin-bottom:8px">
                ${required ? `${__("Required")}: <b>${required} ${unit}</b> &nbsp;|&nbsp;` : ""}
                ${__("Picked")}: <b>${count}</b> ${__("packages")}, <b>${total} ${unit}</b>
                ${diff ? `<span class="text-danger"> &nbsp;(${__("difference")} ${diff > 0 ? "+" : ""}${diff})</span>` : ""}
                ${over.length ? `<div class="text-danger">${__("Issue qty is more than the balance for {0}", [over.map((p) => p.batch_no).join(", ")])}</div>` : ""}
            </div>`);
    }

    // full packages in order until the required qty is met; the last one partly
    function fill_required() {
        let left = required;
        all.forEach((p) => {
            const q = Math.min(flt(p.balance), Math.max(left, 0));
            p.issue_qty = q; p.pick = q > 0 ? 1 : 0; p._was = p.pick; left -= q;
        });
        update();
    }

    function submit() {
        const picked = all.filter((p) => p.pick && flt(p.issue_qty) > 0);
        if (!picked.length) {
            frappe.msgprint(__("Pick at least one package."));
            return;
        }
        const over = picked.filter((p) => flt(p.issue_qty) > flt(p.balance) + 0.0001);
        if (over.length) {
            frappe.msgprint(__("Issue qty is more than the balance for {0}", [over.map((p) => p.batch_no).join(", ")]));
            return;
        }
        custom_ppc.se_split_row(frm, row, picked.map((p) => ({ batch_no: p.batch_no, qty: flt(p.issue_qty) })));
        d.hide();
        frappe.show_alert({ message: __("{0} packages added", [picked.length]), indicator: "green" });
    }

    update();
    custom_ppc.se_close_batch_selector(d);
    d.show();
    setTimeout(() => custom_ppc.se_close_batch_selector(d), 1500);
};

// Replace one row with one row per picked package (qty in stock UOM -> row UOM)
custom_ppc.se_split_row = function (frm, row, picked) {
    const skip = ["name", "idx", "__islocal", "__unsaved", "docstatus", "batch_no", "serial_no",
        "serial_and_batch_bundle"];
    const template = {};
    Object.keys(row).forEach((k) => { if (!skip.includes(k)) template[k] = row[k]; });
    const cf = flt(row.conversion_factor) || 1;

    const apply = (target, p) => Object.assign(target, template, {
        batch_no: p.batch_no, use_serial_batch_fields: 1,
        qty: p.qty / cf, transfer_qty: p.qty,
    });

    apply(row, picked[0]);
    picked.slice(1).forEach((p) => apply(frm.add_child("items"), p));

    const items = frm.doc.items;
    const n = picked.length - 1;
    if (n) {
        const extra = items.splice(items.length - n, n);
        items.splice(row.idx, 0, ...extra);
    }
    items.forEach((it, i) => (it.idx = i + 1));

    frm.refresh_field("items");
    frm.dirty();
};
