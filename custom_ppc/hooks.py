app_name = "custom_ppc"
app_title = "Custom PPC"
app_publisher = "Apnemy Technologies"
app_description = "Package-wise UOM handling (any UOM to any UOM) and production planning & control"
app_email = "ap@apnemy.com"
app_license = "mit"
required_apps = ["erpnext"]

# Custom fields are created/updated on install and on every migrate
after_install = "custom_ppc.install.setup_fields"
after_migrate = "custom_ppc.install.setup_fields"

doctype_js = {
    "Purchase Receipt": "public/js/purchase_receipt.js",
    "Stock Entry": "public/js/stock_entry.js",
}

# Drafts (e.g. created by OCR) can be saved without packages; submit needs them.
doc_events = {
    "Purchase Receipt": {
        "before_submit": "custom_ppc.overrides.check_package_rows",
        "on_submit": "custom_ppc.overrides.link_packages_to_receipt",
    },
    "Stock Entry": {
        "before_validate": "custom_ppc.overrides.require_package_selection",
        "before_submit": "custom_ppc.overrides.check_package_rows",
    },
}
