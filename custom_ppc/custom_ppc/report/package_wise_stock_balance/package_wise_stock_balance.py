# Package-wise Stock Balance
# Full packages (balance == qty per package) are grouped per item + warehouse + tag + unit + size:
#   "3 Roll x 52 Meter = 156 Meter"
# Part-used packages are listed one per line with their balance.
import frappe
from frappe import _
from frappe.utils import flt

from erpnext.stock.doctype.batch.batch import get_batch_qty

FULL, PART, NO_SIZE = "Full", "Part used", "No size"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
        {"label": _("Tag ID"), "fieldname": "tag_id", "fieldtype": "Data", "width": 90},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 85},
        {"label": _("Package(s)"), "fieldname": "package", "fieldtype": "Data", "width": 170},
        {"label": _("Package Unit"), "fieldname": "package_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
        {"label": _("No. of Packages"), "fieldname": "packages", "fieldtype": "Int", "width": 90},
        {"label": _("Qty per Package"), "fieldname": "qty_per_package", "fieldtype": "Float", "width": 100},
        {"label": _("Balance Qty"), "fieldname": "balance", "fieldtype": "Float", "width": 100},
        {"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
    ]


def get_warehouses(filters):
    cond = {"company": filters.company, "is_group": 0}
    if filters.warehouse:
        lft, rgt = frappe.db.get_value("Warehouse", filters.warehouse, ["lft", "rgt"])
        cond.update({"lft": [">=", lft], "rgt": ["<=", rgt]})
    return frappe.get_all("Warehouse", filters=cond, pluck="name")


def get_data(filters):
    warehouses = get_warehouses(filters)
    if not warehouses:
        return []

    item_filters = {"custom_track_by_package": 1, "has_batch_no": 1}
    if filters.item_code:
        item_filters["name"] = filters.item_code
    items = {i.name: i for i in frappe.get_all(
        "Item", filters=item_filters, fields=["name", "item_name", "stock_uom"])}
    if not items:
        return []

    bins = frappe.get_all(
        "Bin",
        filters={"item_code": ["in", list(items)], "warehouse": ["in", warehouses], "actual_qty": [">", 0]},
        fields=["item_code", "warehouse"],
    )

    tag_filter = (filters.tag_id or "").strip().lower()
    out = []
    for b in bins:
        batches = [x for x in (get_batch_qty(item_code=b.item_code, warehouse=b.warehouse) or [])
                   if flt(x.get("qty")) > 0]
        if not batches:
            continue
        details = {d.name: d for d in frappe.get_all(
            "Batch",
            filters={"name": ["in", [x.get("batch_no") for x in batches]]},
            fields=["name", "custom_tag_id", "custom_package_no", "custom_qty_per_package", "custom_package_uom"],
        )}

        groups, parts = {}, []
        for x in batches:
            d = details.get(x.get("batch_no")) or frappe._dict(name=x.get("batch_no"))
            if tag_filter and tag_filter not in (d.custom_tag_id or "").lower():
                continue
            bal, size = flt(x.get("qty")), flt(d.custom_qty_per_package)
            if size and abs(bal - size) < 0.001:
                key = (d.custom_tag_id or "", d.custom_package_uom or "", size)
                groups.setdefault(key, []).append(d.custom_package_no)
            else:
                parts.append((d, bal))

        item = items[b.item_code]
        base = {"item_code": b.item_code, "item_name": item.item_name,
                "warehouse": b.warehouse, "stock_uom": item.stock_uom}

        for (tag, uom, size), nos in groups.items():
            nos = sorted(n for n in nos if n)
            out.append({**base, "tag_id": tag, "status": FULL,
                        "package": ", ".join(f"{n:02d}" for n in nos) if nos else "",
                        "package_uom": uom, "packages": len(nos) or 1,
                        "qty_per_package": size, "balance": size * (len(nos) or 1)})
        for d, bal in parts:
            out.append({**base, "tag_id": d.custom_tag_id, "status": PART if flt(d.custom_qty_per_package) else NO_SIZE,
                        "package": d.name, "package_uom": d.custom_package_uom, "packages": 1,
                        "qty_per_package": d.custom_qty_per_package, "balance": bal})

    out.sort(key=lambda r: (r["item_code"], r["warehouse"], r["tag_id"] or "",
                            0 if r["status"] == FULL else 1, r["package"] or ""))
    return out
