frappe.query_reports["Package-wise Stock Balance"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
          default: frappe.defaults.get_user_default("Company"), reqd: 1 },
        { fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse",
          get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }) },
        { fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item",
          get_query: () => ({ filters: { custom_track_by_package: 1 } }) },
        { fieldname: "tag_id", label: __("Tag ID"), fieldtype: "Data" },
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data) {
            const color = data.status === "Full" ? "green" : data.status === "Part used" ? "orange" : "gray";
            value = `<span style="color: var(--${color}-600, ${color})">${value}</span>`;
        }
        return value;
    },
};
