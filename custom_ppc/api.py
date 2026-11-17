import frappe
from frappe import _
from frappe.utils import flt, cint

from custom_ppc.utils import get_package_info


@frappe.whitelist()
def package_info(item_code):
    """{package_uom, stock_uom} for items tracked by package, else None."""
    return get_package_info(item_code)


@frappe.whitelist()
def create_packages(item_code, lines, purchase_receipt=None):
    """Create one Batch per physical package.

    lines: [{"tag_id": "12345", "packages": 4, "qty": 52, "package_uom": "Roll"}, ...]
           qty = qty per package in the item's stock UOM
           package_uom is optional (defaults to the item's Package Unit)
    Returns: [{"batch_no": ..., "qty": ...}, ...] - one entry per package.
    """
    frappe.has_permission("Batch", "create", throw=True)
    info = get_package_info(item_code)
    if not info:
        frappe.throw(_("{0} is not tracked by package").format(item_code))

    out, next_no = [], {}  # same tag on several lines keeps counting
    for ln in frappe.parse_json(lines):
        tag = (ln.get("tag_id") or "").strip()
        count, qty = cint(ln.get("packages")), flt(ln.get("qty"))
        pkg_uom = ln.get("package_uom") or info.package_uom
        if not tag or count <= 0 or qty <= 0:
            frappe.throw(_("Each line needs Tag ID, No. of packages and Qty per package"))
        start = next_no.get(tag, 1)
        next_no[tag] = start + count
        for n in range(start, start + count):
            name = f"{item_code}-{tag}-{n:02d}"
            if frappe.db.exists("Batch", name):
                frappe.throw(_("Package {0} already exists. Check the Tag ID.").format(name))
            frappe.get_doc({
                "doctype": "Batch",
                "batch_id": name,
                "item": item_code,
                "custom_tag_id": tag,
                "custom_package_no": n,
                "custom_qty_per_package": qty,
                "custom_package_uom": pkg_uom,
                "reference_doctype": "Purchase Receipt" if purchase_receipt else None,
                "reference_name": purchase_receipt,
            }).insert()
            out.append({"batch_no": name, "qty": qty})
    return out


@frappe.whitelist()
def get_packages(item_code, warehouse):
    """Packages of an item with balance > 0 in a warehouse."""
    from erpnext.stock.doctype.batch.batch import get_batch_qty

    rows = []
    for b in get_batch_qty(item_code=item_code, warehouse=warehouse) or []:
        if flt(b.get("qty")) <= 0:
            continue
        tag, no, size, uom = frappe.db.get_value(
            "Batch", b.get("batch_no"),
            ["custom_tag_id", "custom_package_no", "custom_qty_per_package", "custom_package_uom"],
        ) or (None, None, None, None)
        rows.append({"batch_no": b.get("batch_no"), "tag_id": tag, "package_no": no,
                     "qty_per_package": size, "package_uom": uom, "balance": flt(b.get("qty"))})
    return sorted(rows, key=lambda r: (r["tag_id"] or "", r["package_no"] or 0))
