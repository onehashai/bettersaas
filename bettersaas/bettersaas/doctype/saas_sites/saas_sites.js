frappe.ui.form.on("SaaS sites", "after_save", function (frm) {
  frappe.call({
    method:
      "bettersaas.bettersaas.doctype.saas_sites.saas_sites.updateLimitsOfSite",
    args: {
      max_users: frm.doc.user_limit,
      sitename: frm.doc.site_name,
      max_space: frm.doc.space_limit,
      max_email: frm.doc.email_limit,
    },
    callback: function (r) {
      console.log("limits updated", r);
    },
  });
});
// set default values fetched from SaaS settings

// frappe.integrations.doctype.s3_backup_settings.s3_backup_settings.take_backups_s3
frappe.ui.form.on("SaaS sites", {
  refresh: async function (frm) {
		
    frm.add_custom_button(__("Login As Administrator"), async function () {
      // When this button is clicked, do this

      const dec_db_password = (
        await $.ajax({
          url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.getDecryptedPassword",
          type: "GET",
          dataType: "json",
          data: {
            site_name: frm.doc.site_name,
          },
        })
      ).message;
      console.log(dec_db_password);
	    //-------------------------------------------------------------------------------------------------------
        let site_name = frm.doc.site_name;
	// const loginurl = `https://${site_name}/api/method/login?usr=Administrator&pwd=${dec_db_password}`;
	// const mainsite = `https://${site_name}/app`;
	// const loginWindow = window.open(loginurl, "_blank");
	
	// setTimeout(() => {
	//     loginWindow.close();
	//     window.open(mainsite, "_blank");
	// }, 1500);
	const postData = {
  usr: "Administrator",
  pwd: dec_db_password,
};

fetch(`https://${siteName}/api/method/login`, {
  method: "POST",
  body: new URLSearchParams(postData),
  headers: {
    "Content-Type": "application/x-www-form-urlencoded",
  },
})
  .then((response) => response.headers.get("set-cookie"))
  .then((cookie) => {
    const sid = cookie.match(/sid=([^;]*)/);
    if (sid) {
      console.log("SID:", sid[1]);
      // Open a new window with the SID
      window.open(`https://${siteName}/app?sid=${sid[1]}`, '_blank');
    } else {
      console.error("SID not found in the response.");
    }
  })
  .catch((error) => {
    console.error("Error:", error);
  });

	    //------------------------------------------------------------------------------------------------------
      // let enc_password = CryptoJS.enc.Base64.stringify(
      //   CryptoJS.enc.Utf8.parse(dec_db_password)
      // );
      // const query = `?domain=${frm.doc.site_name}&email=Administrator&utm_id=${enc_password}`;

      // // do something with these values, like an ajax request
      // // or call a server side frappe function using frappe.call
      // console.log(query);
      // let site_name = frm.doc.site_name;
      // if (window.location.port == 8000) {
      //   site_name += ":8000";
      // }
      // const urlToRedirect = `http://${site_name}/redirect` + query;
      // console.log(urlToRedirect);
      // window.open(urlToRedirect, "_blank");
    });
    frm.add_custom_button(__("Create Backup"), async function () {
      const { resp } = $.ajax({
        url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.take_backup_of_site",
        type: "GET",
        dataType: "json",
        data: {
          sitename: frm.doc.site_name,
        },
      });
      console.log(resp);
    });
    // set limits
  },
});

frappe.ui.form.on("SaaS sites", "update_limits", function (frm) {
  // create a frappe ui dialog with email limit, space limit, user limit, expiry date
  frappe.prompt(
    [
      {
        fieldname: "email_limit",
        label: "Email Limit",
        fieldtype: "Int",
        default: frm.doc.email_limit,
        reqd: 1,
      },
      {
        fieldname: "space_limit",
        label: "Space Limit",
        fieldtype: "Int",
        default: frm.doc.space_limit.replace("GB", ""),
        description: "Enter in GB ( without the suffix GB )",
        reqd: 1,
      },
      {
        fieldname: "user_limit",
        label: "User Limit",
        fieldtype: "Int",
        default: frm.doc.user_limit == "Unlimited" ? -1 : frm.doc.user_limit,
        reqd: 1,
        description: "Enter -1 for unlimited users",
      },
    ],
    function (values) {
      frappe.call({
        method:
          "bettersaas.bettersaas.doctype.saas_sites.saas_sites.updateLimitsOfSite",
        args: {
          max_users:
            values.user_limit == -1 || values.user_limit == "-1"
              ? 1000000
              : values.user_limit,
          sitename: frm.doc.site_name,
          max_space: values.space_limit,
          max_email: values.email_limit,
          expiry_date: values.expiry_date,
        },
        callback: function (r) {
          console.log("limits updated", r);
        },
      });
    }
  );
});
