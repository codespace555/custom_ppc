# Batch-Wise Package History
# = ERPNext's standard "Batch-Wise Balance History" (same filters, same numbers)
# + package columns (Tag ID, Package No, Package Unit, Qty per Package, Status).
# Status "Open" = package partly used (balance < its size); those rows are highlighted.
# The standard report is not modified, so ERPNext upgrades stay safe.
import frappe
from frappe import _
from frappe.utils import flt

from erpnext.stock.report.batch_wise_balance_history.batch_wise_balance_history import (
    execute as standard_execute,
)

FULL, OPEN, EMPTY, NO_SIZE = "Full", "Open", "Empty", "No size"

PACKAGE_COLUMNS = [
    {"label": _("Tag ID"), "fieldname": "tag_id", "fieldtype": "Data", "width": 90},
    {"label": _("Package No"), "fieldname": "package_no", "fieldtype": "Data", "width": 110},
    {"label": _("Package Unit"), "fieldname": "package_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
    {"label": _("No. of Packages"), "fieldname": "packages", "fieldtype": "Int", "width": 90},
    {"label": _("Qty per Package"), "fieldname": "qty_per_package", "fieldtype": "Float", "width": 100},
    {"label": _("Status"), "fieldname": "package_status", "fieldtype": "Data", "width": 80},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    result = standard_execute(filters)
    # the standard report returns "Label:Type/Options:Width" columns and list rows
    columns = [_to_dict(c) for c in result[0]]
    names = [c["fieldname"] for c in columns]
    data = [r if isinstance(r, dict) else dict(zip(names, r)) for r in (result[1] or [])]

    # package columns right after the Batch column
    pos = next((i + 1 for i, c in enumerate(columns) if _fieldname(c) == "batch"), len(columns))
    columns[pos:pos] = PACKAGE_COLUMNS

    batches = {r.get("batch") for r in data if isinstance(r, dict) and r.get("batch")}
    details = {
        d.name: d
        for d in frappe.get_all(
            "Batch",
            filters={"name": ["in", list(batches)]},
            fields=["name", "custom_tag_id", "custom_package_no", "custom_package_uom", "custom_qty_per_package"],
        )
    } if batches else {}

    tag_filter = (filters.get("tag_id") or "").strip().lower()
    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        d = details.get(row.get("batch")) or frappe._dict()
        if tag_filter and tag_filter not in (d.custom_tag_id or "").lower():
            continue
        size, bal = flt(d.custom_qty_per_package), flt(row.get("balance_qty"))
        if bal <= 0:
            status = EMPTY
        elif not size:
            status = NO_SIZE if d.custom_tag_id else ""
        elif abs(bal - size) < 0.001:
            status = FULL
        else:
            status = OPEN
        if filters.get("open_only") and status != OPEN:
            continue
        row.update({
            "tag_id": d.custom_tag_id,
            "packages": 1,
            "package_no": f"{d.custom_package_no:02d}" if d.custom_package_no else "",
            "package_uom": d.custom_package_uom,
            "qty_per_package": d.custom_qty_per_package,
            "package_status": status,
        })
        out.append(row)

    if filters.get("group_full", 1) in (1, "1", True):
        out = group_unopened(out)
        for c in columns:  # several batches in one cell -> plain text
            if c.get("fieldname") == "batch":
                c.update({"fieldtype": "Data", "options": None, "width": 220})
    return columns, out


SUM_FIELDS = ("opening_qty", "in_qty", "out_qty", "balance_qty", "balance_value", "packages")


def group_unopened(rows):
    """Unopened packages (Full) of the same item + warehouse + tag + unit + size -> one row:
    batches comma-separated, No. of Packages = count, quantities summed.
    Same for packages fully moved out (Empty). Open / No size packages keep their own row,
    so as soon as one package is opened it gets its own line and the group count drops."""
    grouped, order = {}, []
    for r in rows:
        if r.get("package_status") not in ("Full", "Empty"):
            key = ("single", id(r))
        else:
            key = (r.get("item"), r.get("warehouse"), r.get("tag_id"), r.get("package_uom"),
                   flt(r.get("qty_per_package")), r.get("package_status"))
        if key not in grouped:
            grouped[key] = dict(r)
            grouped[key]["_batches"], grouped[key]["_nos"] = [r.get("batch")], [r.get("package_no")]
            order.append(key)
            continue
        g = grouped[key]
        for f in SUM_FIELDS:
            g[f] = flt(g.get(f)) + flt(r.get(f))
        g["_batches"].append(r.get("batch"))
        g["_nos"].append(r.get("package_no"))

    out = []
    for key in order:
        g = grouped[key]
        g["batch"] = ", ".join(b for b in g.pop("_batches") if b)
        g["package_no"] = ", ".join(sorted(n for n in g.pop("_nos") if n))
        if flt(g.get("balance_qty")):
            g["valuation_rate"] = flt(g.get("balance_value")) / flt(g.get("balance_qty"))
        out.append(g)
    return out


def _fieldname(col):
    return col.get("fieldname") if isinstance(col, dict) else None


def _to_dict(col):
    """'Item:Link/Item:100' -> {"label": "Item", "fieldtype": "Link", "options": "Item", "width": 100, ...}"""
    if isinstance(col, dict):
        col = dict(col)
        col.setdefault("fieldname", frappe.scrub(col.get("label") or ""))
        return col
    parts = (col or "").split(":")
    label = parts[0]
    fieldtype, options = "Data", None
    if len(parts) > 1 and parts[1]:
        fieldtype, _sep, options = parts[1].partition("/")
        fieldtype = fieldtype or "Data"
    width = parts[2] if len(parts) > 2 and parts[2] else 100
    return {"label": label, "fieldname": frappe.scrub(label), "fieldtype": fieldtype,
            "options": options or None, "width": width}
