const config = {
  DEFAULT_COUNTRIES: ["US", "IN", "SG", "AE"],
  IPINFO_TOKEN: "3bd603a67da440",
  OTP_RESEND_TIME_SECONDS: 30,
  FEEDBACK: {
    OTP_VERIFIED: "OTP verified successfully",
    VERIFYING_OTP: "Verifying OTP..",
  },
  DOM_ELEMENT_SELECTOR: {
    OTP_FEEDBACK: "otp-feedback",
  },
  ERROR_MESSAGES: {
    ACCEPT_TERMS: "Please accept the terms and conditions",
    INVALID_EMAIL: "Please enter a valid email address",
    INVALID_PASSWORD: "Please enter a valid password",
    INVALID_PHONE: "Please enter a valid phone number",
    INVALID_OTP: "Please enter a valid OTP",
    INVALID_FNAME: "Please enter a valid first Name",
    INVALID_LNAME: "Please enter a valid last Name",
    OTP_EXPIRED: "OTP expired",
    REQUIRED: "This field is required",
    PASSWORD_REQUIRED: "Password cannot be empty",
    SUBDOMAIN_REQUIRED: "Subdomain cannot be empty",
    SUBDOMAIN_NOT_AVAILABLE: "Subdomain is not available",
  },
  SITE_CREATION_POLL_TIME: 3000,
  EMAIL_REGEX: /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/,
  HTTP_METHODS: {
    CHECK_SUBDOMAIN: {
      ENDPOINT:
        "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.check_subdomain",
      METHOD: "GET",
      SUCCESS_MESSAGE: "success",
    },
    CHECK_PASSWORD_STRENGTH: {
      ENDPOINT:
        "/api/method/bettersaas.bettersaas.doctype.saas_sites.saas_sites.check_password_strength",
      METHOD: "GET",
      DATA: {
        PASSWORD: "password",
        FIRST_NAME: "first_name",
        LAST_NAME: "last_name",
        EMAIl: "email",
      },
    },
    CHECK_SITE_CREATED: {
      ENDPOINT:
        "bettersaas.bettersaas.doctype.saas_sites.saas_sites.checkSiteCreated",
      SUCCESS_MESSAGE: "yes",
    },
    SEND_OTP: {
      ENDPOINT:
        "/api/method/bettersaas.bettersaas.doctype.saas_users.saas_users.send_otp",
      METHOD: "GET",
      DATA: {
        PHONE: "phone",
        EMAIl: "email",
        FNAME: "fname",
        CNAME: "company_name",
        LNAME: "lname",
      },
    },
    VERIFY_OTP: {
      ENDPOINT:
        "/api/method/bettersaas.bettersaas.doctype.saas_users.saas_users.verify_account_request",
      METHOD: "GET",
      DATA: {
        UNIQUE_ID: "unique_id",
        OTP: "otp",
      },
      SUCCESS_MESSAGE: "SUCCESS",
    },
    CREATE_SITE: {
      ENDPOINT: "bettersaas.bettersaas.doctype.saas_sites.saas_sites.setupSite",
    },
  },
};
