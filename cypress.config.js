const { defineConfig } = require("cypress");

module.exports = defineConfig({
  projectId: "92odwv",
  adminPassword: "Rohit123##",
  planName: "OneHash Pro",
  testUser: "frappe@example.com",
  defaultCommandTimeout: 20000,
  pageLoadTimeout: 200000,
  video: true,
  videoUploadOnPasses: false,
  chromeWebSecurity: false,
  retries: {
    runMode: 2,
    openMode: 2,
  },
  e2e: {
    experimentalSessionAndOrigin: true,

    // We've imported your old cypress plugins here.
    // ignore support files
    supportFile: "./cypress/support/*index.js",

    // You may want to clean this up later by importing these.
    setupNodeEvents(on, config) {
      return require("./cypress/plugins/index.js")(on, config);
    },
    baseUrl: "http://six.localhost:8000",
    testURL: "http://qewf.localhost:8000",
    specPattern: ["./cypress/integration/*.js", "**/ui_test_*.js"],
  },
});
