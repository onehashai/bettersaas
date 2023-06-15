frappe.listview_settings["SaaS stock sites"] = {
  onload(listview) {
    listview.page.set_secondary_action(
      "Refresh sitess",
      () => refresh(),
      "octicon octicon-sync"
    );
  },
};
function refresh() {
  frappe
    .call(
      "bettersaas.bettersaas.doctype.saas_stock_sites.saas_stock_sites.refreshStockSites"
    )
    .then((r) => {
      frappe.msgprint(r.message);
    });
}
