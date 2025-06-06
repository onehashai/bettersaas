$(document).ready(function () {
  fetch('/api/method/bettersaas.api.get_jwt_token')
    .then(response => response.json())
    .then(data => {
      const token = data.message.token;
      (function(d,t) {
        var BASE_URL = "http://localhost:3000";
        var g = d.createElement(t),
            s = d.getElementsByTagName(t)[0];
        g.src = BASE_URL + "/widget.umd.js";
        g.defer = true;
        g.async = true;
        s.parentNode.insertBefore(g,s);
        g.onload = function() {
          window.CRMCopilotWidget.init({
            user: frappe.session,
            token: token,
          });
        }
      })(document, "script");
    })
    .catch(error => console.error('Error fetching token:', error));
})

window.addEventListener("message", (event) => {
  if (event.data?.type === "copilot-opened") {
    document.body.classList.add("copilot-open");
  }

  if (event.data?.type === "copilot-closed") {
    document.body.classList.remove("copilot-open");
  }
});