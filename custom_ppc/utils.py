import frappe


def get_package_info(item_code):
    """Package settings of an item, or None if it is not tracked by package."""
    if not item_code:
        return None
    track, pkg_uom, stock_uom = frappe.get_cached_value(
        "Item", item_code, ["custom_track_by_package", "custom_package_uom", "stock_uom"]
    ) or (0, None, None)
    if not track:
        return None
    return frappe._dict(package_uom=pkg_uom or "Package", stock_uom=stock_uom)


def is_package_item(item_code):
    return bool(get_package_info(item_code))
