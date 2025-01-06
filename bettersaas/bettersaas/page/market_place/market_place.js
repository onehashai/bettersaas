frappe.pages["market-place"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
	  parent: wrapper,
	  title: "Marketplace",
	  single_column: true,
	});
	$(frappe.render_template("market_place")).appendTo(
	  page.body.addClass("no-border")
	);
	$(document).ready(function () {
	  document.getElementById(
		"app_div"
	  ).innerHTML = `	<div class='d-flex justify-content-center w-100'>
				<div class="spinner-border text-primary" role="status">
				  <span class="visually-hidden"></span>
				</div>
				</div>
		  `;
	  frappe.call({
		method: "bettersaas.bettersaas.page.market_place.market_place.get_all_apps",
		callback: (res) => {
		  document.getElementById("app_div").innerHTML = "";
		  Object.keys(res.message).forEach(function (key, index) {
			document.getElementById("app_div").innerHTML += `
						  <div class="col-md-4 my-2">
						  <div class="card">
						  <div class="card-body" id="div${index}">
							  <div class="col-2 col-sm-2 col-md-4 px-0 mb-3">
							  </div>
				<div style="width: 40px; height: 40px; overflow: hidden; border-radius: 10%">
					<img class="card-title" src="${res.message[key].icon}" style="width: 100%; height: auto;" />
				</div><br>
							  <h4 class="card-title text-dark">${res.message[key].name}</h4>
							  <p class="card-text text-dark">${res.message[key].description}</p>
							  </div>
							  </div> 
						  </div>`;
			if(res.message[key].enabled==1)
			{
				{
				  if (res.message[key].installed == "true") {
					document.getElementById(
					  `div${index}`
					).innerHTML += `<button type="button" class="btn btn-danger" id="btn${index} " name='${res.message[key].app_name}' value="uninstall" >Uninstall <i class="fa fa-remove" aria-hidden="true"></i></button>`;
				  } else {
					document.getElementById(
					  `div${index}`
					).innerHTML += `<button type="button" class="btn btn-primary" id="btn${index} " name=${res.message[key].app_name} value="install" >Install <i class="fa fa-download" aria-hidden="true"></i></button>`;
				  }
				}
			}
			else
			  {
				document.getElementById(
				  `div${index}`
				).innerHTML += `<button type="button" class="btn btn-success" id=" " name='comming_soon' disabled>Comming Soon  ; )</button>`;
			  }
		  });
		},
		error: (err) => {
		  console.log(err);
		},
	  });
	});
  };
  
  $(document).ready(function () {
	$(document).on("click", "button", function () {
	  if (this.value == "install") {
		document.getElementById(
		  `${this.id}`
		).innerHTML = ` <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Installing...`;
		$(":button").prop("disabled", true);
		frappe.call({
		  method: "clientside.clientside.page.market_place.market_place.install_app",
		  args: {
			app_name: this.name,
		  },
		  callback: (res) => {
			document.getElementById(`${this.id}`).innerHTML = "";
			if (res.message == "Success") {
			  frappe.set_route("app", "home");
			  frappe.show_alert("App Installed", 5);
			  window.location.reload();
			} else {
			  frappe.show_alert("No such app available for installation", 5);
			}
			$(":button").prop("disabled", false);
		  },
		  error: (err) => {
			console.log(err);
		  },
		});
	  } else {
		document.getElementById(
		  `${this.id}`
		).innerHTML = ` <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Uninstalling...`;
		$(":button").prop("disabled", true);
		frappe.call({
		  method: "clientside.clientside.page.market_place.market_place.uninstall_app",
		  args: {
			app_name: this.name,
		  },
		  callback: (res) => {
			document.getElementById(`${this.id}`).innerHTML = "";
			if (res.message == "Success") {
			  frappe.set_route("app", "home");
			  frappe.show_alert("App Uninstalled", 5);
			  window.location.reload();
			} else {
			  frappe.show_alert(`Couldn't uninstall the app`, 5);
			}
			$(":button").prop("disabled", false);
		  },
		  error: (err) => {
			console.log(err);
		  },
		});
	  }
	});
  });
  