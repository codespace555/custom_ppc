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
