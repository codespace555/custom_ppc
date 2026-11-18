import frappe
from frappe import _

from custom_ppc.utils import is_package_item


# Stock Entry purposes where raw material is consumed from WIP: ERPNext picks the
# batches itself (FIFO) on submit, so no package selection is required there.
CONSUMPTION_PURPOSES = {
    "Manufacture",
    "Material Consumption for Manufacture",
    "Repack",
    "Disassemble",
}


def check_package_rows(doc, method=None):
    """On submit: rows of package-tracked items must carry a package (batch)."""
    consumption = doc.doctype == "Stock Entry" and doc.get("purpose") in CONSUMPTION_PURPOSES
    for row in doc.get("items") or []:
        if consumption and row.get("s_warehouse"):
            continue  # consumed from WIP - batches picked by ERPNext
        if is_package_item(row.item_code) and not (
            row.get("batch_no") or row.get("serial_and_batch_bundle")
        ):
            frappe.throw(_("Row {0}: {1} is tracked by package. Select the package(s) (batch) for this row first.").format(
                row.idx, row.item_code))


def link_packages_to_receipt(doc, method=None):
    """Record on each package (Batch) the Purchase Receipt it came in on."""
    for row in doc.get("items") or []:
        if row.get("batch_no") and is_package_item(row.item_code):
            if not frappe.db.get_value("Batch", row.batch_no, "reference_name"):
                frappe.db.set_value("Batch", row.batch_no,
                                    {"reference_doctype": doc.doctype, "reference_name": doc.name})


def require_package_selection(doc, method=None):
    """Stock Entry, before ERPNext's own validate: a package row that takes stock out of a
    warehouse must have its package(s) chosen by the user. Without this, ERPNext would
    auto-pick a batch by FIFO on save (Stock Settings: auto create bundle for outward),
    so the user would not control which roll / box is cut.
    Consumption entries (Manufacture etc.) are skipped: there ERPNext picks from WIP."""
    if doc.get("purpose") in CONSUMPTION_PURPOSES:
        return
    for row in doc.get("items") or []:
        if not row.get("s_warehouse") or not is_package_item(row.item_code):
            continue
        if not (row.get("batch_no") or row.get("serial_and_batch_bundle")):
            frappe.throw(
                _("Row {0}: {1} is tracked by package. Choose which package(s) to take "
                  "(Add Batch Nos / Batch No) before saving.").format(row.idx, row.item_code),
                title=_("Package not selected"),
            )
