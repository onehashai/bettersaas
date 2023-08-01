// ignore type errors
Cypress.on("uncaught:exception", (err, runnable) => {
  if (err.message.includes("modal")) {
    return false;
  }
});
