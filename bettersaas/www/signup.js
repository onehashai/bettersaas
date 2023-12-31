// config.js conatins the "config" variable imported through signup.html
function getDomain() {
  let domain = "." + window.location.hostname.split(".").splice(1, 2).join(".");
  if (window.location.port) {
    domain += ":" + window.location.port;
  }
  return domain;
}
window.onload = function () {
  document.getElementById("main").style.visibility = "visible";
  document.getElementById("spinner-bg").style.height = "0vh";
  document.querySelector(".spinner-border").style.visibility = "hidden";
};
VeeValidate.configure({
  validateOnBlur: true, // controls if `blur` events should trigger validation with `handleChange` handler
  validateOnChange: true, // controls if `change` events should trigger validation with `handleChange` handler
  validateOnInput: true, // controls if `input` events should trigger validation with `handleChange` handler
});
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
window.Vue.createApp({
  data() {
    return {
      otp: "",
      otpVerificationStatus: new OTPVerificationStatus(),
      phoneInput: "",
      fname: "",
      lname: "",
      email: "",
      password: "",
      siteCreated: false,
      loading: false,
      sitename: "",
      otpUniqueId: "",
      otpVerified: true,
      phone: "",
      company_name: "",
      targetSubdomain: "",
      otpSent: false,
      country: "",
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
    const phoneInputField = document.querySelector("#phone");
    const phoneInput = window.intlTelInput(phoneInputField, {
      utilsScript:
        "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js",
      initialCountry: "auto",
      preferredCountries: config.DEFAULT_COUNTRIES,
      geoIpLookup: (callback) => {
        $.get(
          "https://ipinfo.io?token=" + config.IPINFO_TOKEN,
          () => {},
          "jsonp"
        ).always((resp) => {
          let countryCode = resp && resp.country ? resp.country : "us";
          // console.log(resp);
          callback(countryCode);
        });
      },
    });
    phoneInputField.addEventListener("countrychange", () => {
      this.country = phoneInput.getSelectedCountryData().iso2.toUpperCase();
    });
    this.phoneInput = phoneInput;
  },
  methods: {
    otpTimer(remainingSeconds) {
      var m = Math.floor(remainingSeconds / 60);
      var s = remainingSeconds % 60;
      m = m < 10 ? "0" + m : m;
      s = s < 10 ? "0" + s : s;
      if (document.getElementById("timer")) {
        document.getElementById("timer").innerText =
          "Wait for " + s + " seconds";
      }
      remainingSeconds -= 1;
      if (remainingSeconds >= 0) {
        setTimeout(() => {
          this.otpTimer(remainingSeconds);
        }, 1000);
        return;
      }
      this.otpVerificationStatus.reset();
    },
    // isTermsChecked(value) {
    //   if (value && value === "no") {
    //     return true;
    //   }
    //   return config.ERROR_MESSAGES.ACCEPT_TERMS;
    // },

    isRequired(value) {
      if (value && value.length > 0) {
        return true;
      }
      return config.ERROR_MESSAGES.REQUIRED;
    },
    isEmailRegex(value) {
      if (value && value.length > 0) {
        const emailRegex = new RegExp(config.EMAIL_REGEX);
        if (emailRegex.test(value)) {
          return true;
        }
        return config.ERROR_MESSAGES.INVALID_EMAIL;
      }
      return config.ERROR_MESSAGES.REQUIRED;
    },
    isPhoneRegex(value) {
      if (!value) {
        return config.ERROR_MESSAGES.REQUIRED;
      }
      if (this.country !== "IN") {
        return true;
      }
      if (value && value.length > 0) {
        if (this.phoneInput.isValidNumber()) {
          return true;
        }
        return config.ERROR_MESSAGES.INVALID_PHONE;
      }
      return config.ERROR_MESSAGES.REQUIRED;
    },

    async onSubmit(values) {
      console.log(values);
      // skip captcha for cypress tests
      if (!window.Cypress) {
        grecaptcha.ready(function () {
          grecaptcha
            .execute("6LeP2esnAAAAAEYxmv3RteO1BTQnQQGf5YASo-qx", {
              action: "submit",
            })
            .then(function (token) {
              // Add your logic to submit to your backend server here.
              console.log(token);
            });
        });
      }

      this.fname = values["first-name"];
      this.lname = values["last-name"];
      this.email = values["email"].toLowerCase();
      this.password = values["password"];
      this.phone = this.phoneInput.getNumber();
      this.company_name = values["company-name"];
      this.sitename = values["site-name"].toLowerCase();
      this.otpVerificationStatus.setSendingOTP();
      this.sendOtp();
    },

    async checkSubdomain(sitename) {
      this.sitename = sitename.replace(/ /g, "-");
      if (!sitename || sitename.length === 0) {
        return config.ERROR_MESSAGES.SUBDOMAIN_REQUIRED;
      }
      try {
        const res = await $.ajax({
          url:
            window.location.origin +
            config.HTTP_METHODS.CHECK_SUBDOMAIN.ENDPOINT,
          type: config.HTTP_METHODS.CHECK_SUBDOMAIN.METHOD,
          data: {
            subdomain: sitename,
          },
        });
        if (
          res.message.status ===
          config.HTTP_METHODS.CHECK_SUBDOMAIN.SUCCESS_MESSAGE
        ) {
          return true;
        } else {
          return config.ERROR_MESSAGES.SUBDOMAIN_NOT_AVAILABLE;
        }
      } catch (error) {
        return config.ERROR_MESSAGES.SUBDOMAIN_NOT_AVAILABLE;
      }
    },

    async checkPasswordStrength(password, { form }) {
      if (!password) {
        return config.ERROR_MESSAGES.PASSWORD_REQUIRED;
      }
      const { message } = await $.ajax({
        url: config.HTTP_METHODS.CHECK_PASSWORD_STRENGTH.ENDPOINT,
        type: config.HTTP_METHODS.CHECK_PASSWORD_STRENGTH.METHOD,
        data: {
          [config.HTTP_METHODS.CHECK_PASSWORD_STRENGTH.DATA.PASSWORD]: password,
          [config.HTTP_METHODS.CHECK_PASSWORD_STRENGTH.DATA.FIRST_NAME]:
            form["first-name"] || "",
          [config.HTTP_METHODS.CHECK_PASSWORD_STRENGTH.DATA.LAST_NAME]:
            form["last-name"] || "",
          [config.HTTP_METHODS.CHECK_PASSWORD_STRENGTH.DATA.EMAIl]:
            form["email"] || "",
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
        method: config.HTTP_METHODS.CHECK_SITE_CREATED.ENDPOINT,
        args: {
          doc: {
            site_name: this.sitename,
          },
        },
        async: false,
        callback: (r) => {
          if (
            r.message == config.HTTP_METHODS.CHECK_SITE_CREATED.SUCCESS_MESSAGE
          ) {
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
        const query = `?domain=${this.sitename}&email=${this.email}&utm_id=${enc_password}&firstname=${this.fname}&lastname=${this.lname}&companyname=${this.company_name}&country=${this.country}&createUser=true`;
        this.status.step2 = "completed";
        setTimeout(() => {
          this.status.step3 = "completed";
          let siteToRedirect = "";
          if (window.dev_server) {
            siteToRedirect = this.targetSubdomain;
          } else {
            siteToRedirect = this.sitename;
          }
          domainToRedirect = this.sitename;
          
          window.location.href =
            `${
              window.location.protocol
            }//${siteToRedirect}${getDomain()}/redirect` + query;
        }, 1500);
        // const urlToRedirect = `http://app.onehash.is/redirect`;
    
        // window.open(urlToRedirect, "_blank");
      } else {
        setTimeout(() => {
          this.checkSiteCreatedPoll();
        }, config.SITE_CREATION_POLL_TIME);
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
      if (!window.dev_server) {
        const resp = await $.ajax({
          url: config.HTTP_METHODS.SEND_OTP.ENDPOINT,
          type: config.HTTP_METHODS.SEND_OTP.METHOD,
          data: {
            [config.HTTP_METHODS.SEND_OTP.DATA.EMAIl]: this.email,
            [config.HTTP_METHODS.SEND_OTP.DATA.PHONE]: t_phone.replace("+", ""),
            [config.HTTP_METHODS.SEND_OTP.DATA.FNAME]: this.fname,
            [config.HTTP_METHODS.SEND_OTP.DATA.CNAME]: this.company_name,
            [config.HTTP_METHODS.SEND_OTP.DATA.LNAME]: this.lname,
          },
        });
        message = resp.message;
      } else {
        message = "123456";
      }

      this.otpUniqueId = message;
      this.otpVerificationStatus.setOTPSent();
      this.otpTimer(config.OTP_RESEND_TIME_SECONDS);
      this.otpVerificationStatus.sendingOTP = false;
    },
    async verifyOTP() {
      const otp = this.otp;
      if (otp.length !== 6) {
        return;
      }
      this.otpVerificationStatus.setVerifyingOTP();
      document.getElementById(
        config.DOM_ELEMENT_SELECTOR.OTP_FEEDBACK
      ).innerHTML = config.FEEDBACK.VERIFYING_OTP;
      if (!this.isEmailRegex(this.email)) {
        return config.ERROR_MESSAGES.INVALID_EMAIL;
      }
      let message;
      if (!window.dev_server) {
        const resp = await $.ajax({
          url: config.HTTP_METHODS.VERIFY_OTP.ENDPOINT,
          type: config.HTTP_METHODS.VERIFY_OTP.METHOD,
          data: {
            [config.HTTP_METHODS.VERIFY_OTP.DATA.UNIQUE_ID]: this.otpUniqueId,
            [config.HTTP_METHODS.VERIFY_OTP.DATA.OTP]: otp,
          },
        });
        message = resp.message;
      } else {
        message = config.HTTP_METHODS.VERIFY_OTP.SUCCESS_MESSAGE;
      }
      console.log(message);
      if (message === config.HTTP_METHODS.VERIFY_OTP.SUCCESS_MESSAGE) {
        this.otpVerificationStatus.otpVerified = true;
        document.getElementById(
          config.DOM_ELEMENT_SELECTOR.OTP_FEEDBACK
        ).innerHTML = config.FEEDBACK.OTP_VERIFIED;
        this.createSite();
      } else if (message === "OTP_EXPIRED") {
        document.getElementById(
          config.DOM_ELEMENT_SELECTOR.OTP_FEEDBACK
        ).innerHTML = config.ERROR_MESSAGES.OTP_EXPIRED;
      } else if (message == "INVALID_OTP") {
        document.getElementById(
          config.DOM_ELEMENT_SELECTOR.OTP_FEEDBACK
        ).innerHTML = config.ERROR_MESSAGES.INVALID_OTP;
      }
      this.otpVerificationStatus.verifyingOTP = false;
      return true;
    },

    async createSite() {
      this.loading = true;
      this.status.step1 = "active";
      frappe.call({
        method: config.HTTP_METHODS.CREATE_SITE.ENDPOINT,
        args: {
          company_name: this.company_name,
          subdomain: this.sitename.replace(/ /g, "-"),
          password: this.password,
          email: this.email,
          first_name: this.fname,
          last_name: this.lname,
          phone: this.phone,
          country: this.country,
          allow_creating_users: "yes",
        },
        callback: (r) => {
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
