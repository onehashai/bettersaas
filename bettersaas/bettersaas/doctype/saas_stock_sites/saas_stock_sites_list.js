frappe.listview_settings["SaaS Stock Sites"] = {
  onload(listview) {
    listview.page.set_secondary_action(
      "Refresh sites",
      () => refresh(),
      "octicon octicon-sync"
    );
  },
};
function refresh() {
  frappe
    .call(
      "bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.refresh_stock_sites"
    )
    .then((r) => {
      frappe.msgprint(r.message);
    });
}
