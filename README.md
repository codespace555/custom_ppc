# Custom PPC

Package-wise UOM handling for ERPNext v15: **any package UOM to any stock UOM**
(Roll -> Meter, Thaan -> Meter, Box -> Nos, Cone -> Kg ...), for receipt, transfer
and (next) production.

Each physical package = one ERPNext **Batch** holding its qty in the item's stock UOM.

## Setup per item
- **Track by Package** = on
- **Package Unit** = the UOM of the physical package (Roll, Box, Cone ...)
- Has Batch No = on, Automatically Create New Batch = off (the app creates the batches)

## What this version contains
- Item fields: Material Category, Track by Package, Package Unit (copied to variants)
- Batch fields: Tag ID, Package No, Qty per Package, Package Unit
- Purchase Receipt popup ("Enter Packages"): Tag ID / No. of packages / Qty per package
- API: `custom_ppc.api.create_packages`, `custom_ppc.api.get_packages`
- On submit: package rows must carry a batch; batches are linked to their receipt
- Placeholders: Stock Entry / production popup, Package-wise Stock Balance report

## Install (local bench)
```bash
cd frappe-bench
ln -s /mnt/c/Users/NamanKumar/Documents/roll-master-app/custom_ppc apps/custom_ppc
./env/bin/pip install -e apps/custom_ppc
grep -qx custom_ppc sites/apps.txt || echo custom_ppc >> sites/apps.txt
bench --site <site> install-app custom_ppc
bench build --app custom_ppc
```

## Deploy on Frappe Cloud
Push to a private GitHub repo -> Bench Group -> Apps -> Add App -> Deploy -> Site -> Install App.
