// Same filters as ERPNext's Batch-Wise Balance History, plus Tag ID and "Only open packages".
frappe.query_reports["Batch-Wise Package History"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
          default: frappe.defaults.get_user_default("Company"), reqd: 1 },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
          default: frappe.datetime.add_months(frappe.datetime.get_today(), -1), reqd: 1 },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
          default: frappe.datetime.get_today(), reqd: 1 },
        { fieldname: "item_code", label: __("Item Code"), fieldtype: "Link", options: "Item",
          get_query: () => ({ filters: { has_batch_no: 1 } }) },
        { fieldname: "warehouse_type", label: __("Warehouse Type"), fieldtype: "Link", options: "Warehouse Type" },
        { fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse",
          get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }) },
        { fieldname: "batch_no", label: __("Batch No"), fieldtype: "Link", options: "Batch",
          get_query: () => {
              const item_code = frappe.query_report.get_filter_value("item_code");
              return { filters: item_code ? { item: item_code } : {} };
          } },
        { fieldname: "tag_id", label: __("Tag ID"), fieldtype: "Data" },
        { fieldname: "open_only", label: __("Only open packages"), fieldtype: "Check" },
    ],

    // Open (part-used) packages: whole row highlighted; status shown as a coloured label
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;
        if (column.fieldname === "package_status" && data.package_status) {
            const colors = { Open: "orange", Full: "green", Empty: "gray", "No size": "gray" };
            return `<span class="indicator-pill ${colors[data.package_status] || "gray"}">${data.package_status}</span>`;
        }
        if (data.package_status === "Open") {
            return `<div style="background: var(--bg-orange, #fff4e5); font-weight: 600;
                        margin: -4px -8px; padding: 4px 8px;">${value}</div>`;
        }
        return value;
    },
};
