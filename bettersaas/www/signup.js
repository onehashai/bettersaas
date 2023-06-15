const { createApp } = Vue;
let TESTING = false;

domain = "";
if (window.dev_server) {
  domain = ".localhost:8000";
} else {
  domain = ".onehash.io";
}
createApp({
  data() {
    return {
      terms: false,
      validate: "",
      phoneInput: "",
      fname: "",
      lname: "",
      email: "",
      password: "",
      siteCreated: false,
      loading: false,
      sitename: "",
      otpVerified: true,
      phone: "",
      company_name: "",
      inputErrors: [],
      targetSubdomain: "",
      otpSent: false,
      sendOtpButtonDisabled: true,
      country: "",
      enc_password: "",
      status: {
        step1: "neutral",
        step2: "neutral",
        step3: "neutral",
      },
    };
  },
  async created() {
    console.log("created");
  },
  async mounted() {
    if (true) {
      this.fname = "test";
      this.lname = "test";
      this.email = Math.random().toString(36).substring(7) + "@test.com";
      this.password = "Rohit123";
      this.company_name = "Test Company";
      this.phone = "6203861756";
      this.sitename = Math.random().toString(36).substring(7);
      this.terms = true;
    }
    const inputFields = document.querySelectorAll("input");
    inputFields.forEach((input) => {
      document.getElementById(input.id).addEventListener("focus", () => {
        console.log(input.id);
        if (document.getElementById(input.id + "-feedback")) {
          document.getElementById(input.id + "-feedback").remove();
        }
      });
    });

    const phoneInputField = document.querySelector("#phone");
    const p = this;
    const phoneInput = window.intlTelInput(phoneInputField, {
      utilsScript:
        "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js",
      initialCountry: "auto",
      preferredCountries: ["US", "IN", "SG"],
      utilsScript:
        "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js",
      geoIpLookup: (callback) => {
        $.get(
          "https://ipinfo.io?token=3bd603a67da440",
          () => {},
          "jsonp"
        ).always((resp) => {
          console.log(this);
          p.country = resp.country;
          p.setcountry(resp.country);
          let countryCode = resp && resp.country ? resp.country : "us";
          callback(countryCode);
        });
      },
    });
    this.phoneInput = phoneInput;
    const validate = new window.JustValidate("#form", {
      validateBeforeSubmitting: false,
    });

    validate.addField("#first-name", [
      {
        rule: "required",
      },
    ]);
    validate.addField("#last-name", [
      {
        rule: "required",
      },
    ]);
    validate.addField("#email", [
      {
        rule: "required",
      },
      {
        rule: "email",
      },
    ]);
    validate.addField("#company-name", [
      {
        rule: "required",
      },
    ]);

    console.log(document.getElementById("site-name"));

    this.validate = validate;
  },
  methods: {
    setcountry(value) {
      this.country = value;
    },
    async onSubmit() {
      console.log(this.phoneInput);
      this.checkSubdomain(null);
      this.passWordCheckCallPromise();
      this.checkPhone();
      const errorClasses = [
        ".long-feedback",
        ".just-validate-error-label",
        ".error-feedback",
      ];
      for (let i = 0; i < errorClasses.length; i++) {
        const errorNodes = document.querySelectorAll(errorClasses[i]);
        if (errorNodes.length > 0) {
          return;
        }
      }
      // replace all space in sitename with -
      this.createSite();
    },
    removeFeedback(parentId) {
      if (document.getElementById(parentId + "-feedback")) {
        document.getElementById(parentId + "-feedback").remove();
      }
    },
    async checkPassWord(resolve) {},
    addFeedbackNode(parentId, message, isSuccess = false, extraClasses = []) {
      this.removeFeedback(parentId);
      const errorNode = document.createElement("div");
      errorNode.classList.add("feedback");
      if (isSuccess) {
        errorNode.classList.add("success-feedback");
      } else {
        errorNode.classList.add("error-feedback");
      }
      errorNode.id = parentId + "-feedback";
      errorNode.textContent = message;
      errorNode.classList.add(...extraClasses);
      document.getElementById(parentId).parentNode.appendChild(errorNode);
    },
    checkPhone() {
      this.removeFeedback("phone");
      if (this.phone.length === 10) {
        this.addFeedbackNode("phone", "Phone number is valid", true);
      } else {
        this.addFeedbackNode("phone", "Phone number is not valid");
      }
    },
    async checkSubdomain(e, resolve = null) {
      this.sitename = this.sitename.replace(/\s+/g, "-").toLowerCase();
      console.log("check subdomain", resolve);
      this.removeFeedback("site-name");
      if (this.sitename.length === 0) {
        this.addFeedbackNode("site-name", "Subdomain cannot be empty");
        return;
      }
      frappe.call({
        method:
          "bettersaas.bettersaas.doctype.saas_sites.saas_sites.check_subdomain",
        args: {
          subdomain: this.sitename,
        },
        callback: (r) => {
          console.log(r);
          if (r.message.status == "success") {
            this.addFeedbackNode("site-name", "Subdomain is available", true);
          } else {
            this.addFeedbackNode("site-name", "Subdomain is not available");
          }
        },
      });
    },

    checkEmailFormatWIthRegex(email) {
      const regex = /\S+@\S+\.\S+/;
      const p = regex.test(email);
      console.log(p);
      return p;
    },
    async passWordCheckCallPromise() {
      frappe.call({
        method:
          "bettersaas.bettersaas.doctype.saas_sites.saas_sites.check_password_strength",
        args: {
          password: this.password,
          first_name: this.fname,
          last_name: this.lname,
          email: this.email,
        },
        callback: (r) => {
          console.log(r);
          if (Object.keys(r).length === 0) {
            this.addFeedbackNode("password", "Password is required");
            return;
          }

          if (r.message.feedback.password_policy_validation_passed) {
            this.addFeedbackNode("password", "Good to go", true);
          } else {
            console.log("Password is weak");
            this.addFeedbackNode(
              "password",
              r.message.feedback.suggestions.join("."),
              false,
              ["long-feedback"]
            );
          }
        },
      });
    },
    checkSiteCreated() {
      let response;
      frappe.call({
        method:
          "bettersaas.bettersaas.doctype.saas_sites.saas_sites.checkSiteCreated",
        args: {
          doc: {
            site_name: this.sitename,
          },
        },
        async: false,
        callback: (r) => {
          if (r.message == "yes") {
            this.siteCreated = true;
          }
          response = r.message;
        },
      });
      return response;
    },
    checkSiteCreatedPoll() {
      console.log("polling site creation");
      this.checkSiteCreated();
      if (this.siteCreated) {
        this.status.step3 = "completed";
        const pass = this.password.replaceAll(/#/g, "%23");
        console.log(frappe.conf);
        enc_password = CryptoJS.enc.Base64.stringify(
          CryptoJS.enc.Utf8.parse(pass)
        );
        console.log(this);
        const query = `?domain=${this.sitename}&email=${this.email}&password=${enc_password}&firstname=${this.fname}&lastname=${this.lname}&companyname=${this.company_name}&country=${this.country}&createUser=true`;
        console.log(this.ipRespo);
        setTimeout(() => {
          let domainToRedirect = "";
          if (window.dev_server) {
            domainToRedirect = this.targetSubdomain;
          } else {
            domainToRedirect = this.sitename;
          }
          domainToRedirect = this.sitename;
          window.location.href =
            `http://${domainToRedirect}${domain}/redirect` + query;
        }, 2000);
      } else {
        setTimeout(() => {
          this.checkSiteCreatedPoll();
        }, 3000);
      }
    },
    async sendOTP() {
      console.log("sending otp");
      frappe.call({
        method: "bettersaas.bettersaas.doctype.saas_users.saas_users.send_otp",
        args: {
          email: this.email,
        },
        callback: (r) => {
          console.log(r.message);
          if (r.message == "success") {
            this.otpSent = true;
          }
        },
      });
    },
    verifyOTP() {
      frappe.call({
        method:
          "setup_app.setup_app.doctype.saas_users.saas_users.verify_account_request",
        args: {
          email: this.email,
          otp: this.otp,
        },
        callback: (r) => {
          console.log(r.message);
          if (r.message == "success") {
            this.otpVerified = true;
          }
        },
      });
    },

    async createSite() {
      this.loading = true;
      this.status.step1 = "loading";
      frappe.call({
        method: "bettersaas.bettersaas.doctype.saas_sites.saas_sites.setupSite",
        args: {
          doc: {
            company_name: this.company_name,
            subdomain: this.sitename,
            password: this.password,
            email: this.email,
            first_name: this.fname,
            last_name: this.lname,
          },
        },
        callback: (r) => {
          console.log("functon called", r);
          this.status.step1 = "completed";
          this.status.step2 = "completed";
          if (r.message) {
            this.targetSubdomain = r.message.subdomain;
            this.checkSiteCreatedPoll();
          }
        },
      });
    },
  },
}).mount("#main");
