const { createApp } = Vue;
let TESTING = false;
domain = "";
if (window.dev_server) {
  domain = ".localhost:8000";
} else {
  domain = ".onehash.store";
}
VeeValidate.configure({
  validateOnBlur: true, // controls if `blur` events should trigger validation with `handleChange` handler
  validateOnChange: true, // controls if `change` events should trigger validation with `handleChange` handler
  validateOnInput: true, // controls if `input` events should trigger validation with `handleChange` handler
});
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
  components: {
    VForm: VeeValidate.Form,
    VField: VeeValidate.Field,
    ErrorMessage: VeeValidate.ErrorMessage,
  },

  async mounted() {
    //  const inputFields = document.querySelectorAll("input");
    const inputFields = [];
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
  },
  methods: {
    setcountry(value) {
      this.country = value;
    },

    isTermsChecked(value) {
      console.log(value);
      if (value && value === "no") {
        return true;
      }
      return "Please accept the terms and conditions";
    },

    isRequired(value) {
      if (value && value.length > 0) {
        return true;
      }
      return "This field is required";
    },
    isEmailRegex(value) {
      if (value && value.length > 0) {
        const emailRegex = new RegExp(
          "^[a-zA-Z0-9._:$!%-]+@[a-zA-Z0-9.-]+.[a-zA-Z]$"
        );
        if (emailRegex.test(value)) {
          return true;
        }
        return "Please enter a valid email";
      }
      return "This field is required";
    },
    isPhoneRegex(value) {
      if (value && value.length > 0) {
        const phoneRegex = new RegExp("^[0-9]{10}$");
        if (phoneRegex.test(value)) {
          return true;
        }
        return "Please enter a valid phone number";
      }
      return "This field is required";
    },

    async onSubmit(values) {
      console.log("onSubmit", values);
      this.fname = values["first-name"];
      this.lname = values["last-name"];
      this.email = values["email"];
      this.password = values["password"];
      this.phone = values["phone"];
      this.company_name = values["company-name"];
      this.sitename = values["site-name"];
      this.createSite();
    },

    async checkSubdomain(sitename) {
      console.log("checkSubdomain", sitename);
      const admin_url = window.location.origin;
      if (!sitename) {
        return "subdomain cannot be empty";
      }
      if (sitename.length === 0) {
        console.log("sitename", sitename);
        return "subdomain cannot be empty";
      }
      try {
        const res = await $.ajax({
          url: `${admin_url}/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.check_subdomain`,
          type: "GET",
          data: {
            subdomain: sitename,
          },
        });
        if (res.message.status === "success") {
          return true;
        } else {
          return "Subdomain is not available";
        }
      } catch (error) {
        console.log(error);
        return "Subdomain is not available";
      }
    },

    checkEmailFormatWIthRegex(email) {
      const regex = /\S+@\S+\.\S+/;
      const p = regex.test(email);
      console.log(p);
      return p;
    },
    async passWordCheckCallPromise(password, { form }) {
      if (!password) {
        return "Password cannot be empty";
      }
      const { message } = await $.ajax({
        url: "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.check_password_strength",
        type: "GET",
        data: {
          password: password,
          first_name: form["first-name"] || "",
          last_name: form["last-name"] || "",
          email: form["email"] || "",
        },
      });
      if (message.feedback.password_policy_validation_passed) {
        return true;
      }
      return message.feedback.suggestions.join(" .");
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

          if (r.message.subdomain) {
            this.targetSubdomain = r.message.subdomain;
            this.status.step1 = "completed";
            this.status.step2 = "completed";
            this.checkSiteCreatedPoll();
          } else {
            this.status.step1 = "failed";
            this.loading = false;
          }
        },
        error: (e) => {
          this.status.step1 = "failed";
          this.loading = false;
        },
      });
    },
  },
}).mount("#main");
