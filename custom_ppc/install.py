import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Custom PPC"

CUSTOM_FIELDS = {
    "Item": [
        {"fieldname": "custom_category", "label": "Category", "fieldtype": "Select",
         "options": "\nFabric\nTrims\nPacking\nOther", "insert_after": "item_group",
         "in_standard_filter": 1, "module": MODULE},
        {"fieldname": "custom_track_by_package", "label": "Track by Package", "fieldtype": "Check",
         "insert_after": "custom_category", "in_standard_filter": 1,
         "description": "Each physical package (roll, box, cone ...) is kept as its own batch",
         "module": MODULE},
        {"fieldname": "custom_package_uom", "label": "Package Unit", "fieldtype": "Link",
         "options": "UOM", "insert_after": "custom_track_by_package",
         "depends_on": "eval:doc.custom_track_by_package",
         "mandatory_depends_on": "eval:doc.custom_track_by_package",
         "description": "UOM of the physical package, e.g. Roll, Box, Cone", "module": MODULE},
    ],
    "Batch": [
        {"fieldname": "custom_tag_id", "label": "Tag ID", "fieldtype": "Data",
         "insert_after": "item_name", "in_list_view": 1, "in_standard_filter": 1,
         "search_index": 1, "module": MODULE},
        {"fieldname": "custom_package_no", "label": "Package No", "fieldtype": "Int",
         "insert_after": "custom_tag_id", "in_list_view": 1, "module": MODULE},
        {"fieldname": "custom_qty_per_package", "label": "Qty per Package", "fieldtype": "Float",
         "insert_after": "custom_package_no", "in_list_view": 1,
         "description": "Qty in the item's stock UOM when the package was received", "module": MODULE},
        {"fieldname": "custom_package_uom", "label": "Package Unit", "fieldtype": "Link",
         "options": "UOM", "insert_after": "custom_qty_per_package", "module": MODULE},
    ],
}

# copied from template to variants
VARIANT_FIELDS = ["custom_category", "custom_track_by_package", "custom_package_uom"]

# fields left behind by the earlier roll_master app
OBSOLETE_FIELDS = ["Item Group-custom_category", "Batch-custom_roll_no", "Batch-custom_metres_per_roll"]


def setup_fields():
    create_custom_fields(CUSTOM_FIELDS, update=True)
    for name in OBSOLETE_FIELDS:
        if frappe.db.exists("Custom Field", name):
            frappe.delete_doc("Custom Field", name, ignore_permissions=True)
    copy_fields_to_variants()
    frappe.db.commit()


def copy_fields_to_variants():
    ivs = frappe.get_single("Item Variant Settings")
    existing = {f.field_name for f in ivs.fields}
    missing = [f for f in VARIANT_FIELDS if f not in existing]
    for f in missing:
        ivs.append("fields", {"field_name": f})
    if missing:
        ivs.save(ignore_permissions=True)
