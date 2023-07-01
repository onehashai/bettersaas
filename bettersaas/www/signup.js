const { createApp } = Vue;
let TESTING = false;
let domain = "." + window.location.hostname.split(".").splice(1, 2).join(".");
if (window.location.port) {
  domain += ":" + window.location.port;
}
console.log("domain", domain);
const http_protocol = window.location.protocol;
VeeValidate.configure({
  validateOnBlur: true, // controls if `blur` events should trigger validation with `handleChange` handler
  validateOnChange: true, // controls if `change` events should trigger validation with `handleChange` handler
  validateOnInput: true, // controls if `input` events should trigger validation with `handleChange` handler
});
let timerOn = true;

class OTPVerificationStatus {
  constructor() {
    this.otpVerified = false;
    this.reset();
  }
  reset() {
    if (document.getElementById("timer")) {
      document.getElementById("timer").innerText = "";
    }

    this.otpSent = false;
    this.otpUniqueId = "";
    this.verifyingOTP = false;
    this.waitingForResend = false;
    this.sendingOTP = false;
  }
  setOTPVerified() {
    this.otpVerified = true;
  }

  setOTPSent() {
    this.otpSent = true;
  }
  setUniqueId(id) {
    this.otpUniqueId = id;
  }
  setVerifyingOTP() {
    this.verifyingOTP = true;
  }
  setWaitingForResend() {
    this.waitingForResend = true;
  }
  setSendingOTP() {
    this.sendingOTP = true;
  }
}
createApp({
  data() {
    return {
      otp: "",
      otpVerificationStatus: new OTPVerificationStatus(),
      showSubmitbtn: false,
      terms: false,
      validate: "",
      phoneInput: "",
      fname: "",
      isOTPButtonDisabled: false,
      lname: "",
      submiitBtnText: "Submit",
      email: "",
      password: "",
      siteCreated: false,
      loading: false,
      sitename: "",
      otpUniqueId: "",
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
      preferredCountries: ["US", "IN", "SG", "AE"],
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
    phoneInputField.addEventListener("countrychange", () => {
      this.country = phoneInput.getSelectedCountryData().iso2.toUpperCase();
      console.log(phoneInput.isValidNumber());
      this.setcountry(this.country);
      console.log(this.country);
    });
    this.phoneInput = phoneInput;
  },
  methods: {
    timer(remaining) {
      var m = Math.floor(remaining / 60);
      var s = remaining % 60;

      m = m < 10 ? "0" + m : m;
      s = s < 10 ? "0" + s : s;
      document.getElementById("timer").innerText = "Wait for " + s + " seconds";
      remaining -= 1;

      if (remaining >= 0 && timerOn) {
        setTimeout(() => {
          this.timer(remaining);
        }, 1000);
        return;
      }

      if (!timerOn) {
        // Do validate stuff here
        return;
      }

      // Do timeout stuff here
      this.otpVerificationStatus.reset();
    },
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
      if (!value) {
        return "This field is required";
      }
      const cc = this.phoneInput.getSelectedCountryData().iso2.toUpperCase();
      if (cc !== "IN") {
        return true;
      }
      if (value && value.length > 0) {
        if (this.phoneInput.isValidNumber()) {
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
      this.phone = this.phoneInput.getNumber();
      this.company_name = values["company-name"];
      this.sitename = values["site-name"];
      this.otpVerificationStatus.setSendingOTP();
      this.sendOtp();
    },

    async checkSubdomain(sitename) {
      console.log("checkSubdomain", sitename);
      const admin_url = window.location.origin;
      this.sitename = sitename.replace(/ /g, "-");
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
        this.status.step2 = "completed";

        setTimeout(() => {
          this.status.step3 = "completed";
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
    async sendOtp() {
      if (!this.isEmailRegex(this.email)) {
        return;
      }
      let t_phone = "";
      if (this.phoneInput.isValidNumber()) {
        t_phone = this.phoneInput.getNumber();
      }

      frappe.show_alert("Please check your email for OTP", 5);
      // send otp and set otpSent to tru;
      let message;
      console.log(window.dev_server);
      if (!window.dev_server) {
        const resp = await $.ajax({
          url: "/api/method/bettersaas.bettersaas.doctype.saas_users.saas_users.send_otp",
          type: "GET",
          data: {
            email: this.email,
            phone: t_phone.replace("+", ""),
          },
        });
        message = resp.message;
      } else {
        message = "123456";
      }

      this.otpUniqueId = message;
      this.otpVerificationStatus.setOTPSent();
      console.log(this.otpVerificationStatus.otpSent);
      this.timer(10);
      this.otpVerificationStatus.sendingOTP = false;
    },
    async verifyOTP() {
      const otp = this.otp;
      if (otp.length !== 6) {
        return;
      }
      console.log("verifying otp");
      this.otpVerificationStatus.setVerifyingOTP();
      document.getElementById("otp-feedback").innerHTML = "verifying OTP ..";
      if (!this.isEmailRegex(this.email)) {
        return "Email is not valid";
      }
      let message;
      if (!window.dev_server) {
        const resp = await $.ajax({
          url: "/api/method/bettersaas.bettersaas.doctype.saas_users.saas_users.verify_account_request",
          type: "GET",
          data: {
            unique_id: this.otpUniqueId,
            otp: otp,
          },
        });
        message = resp.message;
      } else {
        message = "SUCCESS";
      }
      console.log(message);
      if (message === "SUCCESS") {
        this.otpVerificationStatus.otpVerified = true;
        document.getElementById("otp-feedback").innerHTML = "OTP verified";
        this.createSite();
      } else if (message === "OTP_EXPIRED") {
        document.getElementById("otp-feedback").innerHTML = "OTP Expired";
      } else if (message == "INVALID_OTP") {
        document.getElementById("otp-feedback").innerHTML = "OTP Incorrect";
      }
      this.otpVerificationStatus.verifyingOTP = false;
      console.log(message);
      return true;
    },

    async createSite() {
      this.loading = true;
      this.status.step1 = "active";
      frappe.call({
        method: "bettersaas.bettersaas.doctype.saas_sites.saas_sites.setupSite",
        args: {
          doc: {
            company_name: this.company_name,
            subdomain: this.sitename.replace(/ /g, "-"),
            password: this.password,
            email: this.email,
            first_name: this.fname,
            last_name: this.lname,
            phone: this.phone,
          },
        },
        callback: (r) => {
          console.log("functon called", r);

          if (r.message.subdomain) {
            this.targetSubdomain = r.message.subdomain;
            this.status.step1 = "completed";
            this.status.step2 = "active";
            setTimeout(() => {
              this.status.step2 = "completed";
              this.status.step3 = "active";
            }, 1500);

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
