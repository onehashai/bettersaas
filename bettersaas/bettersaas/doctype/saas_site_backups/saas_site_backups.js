// Copyright (c) 2023, OneHash and contributors
// For license information, please see license.txt

frappe.ui.form.on("SaaS site backups", {
  refresh(frm) {
    frm.add_custom_button(__("Restore site"), async function () {
      await $.ajax({
        url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.restore_site",
        type: "GET",
        dataType: "json",
        data: {
          backupid: frm.doc.name,
          site_name: frm.doc.site,
        },
      });
      console.log(resp);
      frappe.realtime.on("site_restored", function (data) {
        frappe.msgprint("Site restored successfully", data);
      });
    });
    frm.add_custom_button(__("Create site from backup"), async function () {
      // open a dialog box and ask new site name
      //   let d = new frappe.ui.Dialog({
      //     title: "Enter new site details",
      //     fields: [
      //       {
      //         label: "New site name",
      //         fieldname: "site_name",
      //         fieldtype: "Data",
      //       },
      //       {
      //         label: "Last Name",
      //         fieldname: "last_name",
      //         fieldtype: "Data",
      //       },
      //       {
      //         label: "Age",
      //         fieldname: "age",
      //         fieldtype: "Int",
      //       },
      //     ],
      //     size: "small", // small, large, extra-large
      //     primary_action_label: "Submit",
      //     primary_action(values) {
      //       console.log(values);
      //       d.hide();
      //     },
      //   });
    });
  },
});
