// test signup flow of the app
// visit "/signup"
// fill random email, password, full name , company name , otp and submit
// "processing" should be shown
// after some time page should redirect to /redirect
// after some time page should redirect to /app

// Path: apps/bettersaas/cypress/integrations/signup.js
context("Signup", () => {
  it("should signup", () => {
    cy.visit("/signup");
    cy.get("input[name='email']").type("test@test.com");
    cy.get("input[name='password']").type("Rohit123##");
    cy.get("input[name='full_name']").type("Rohit");
    cy.get("input[name='company_name']").type("Samsonite");
    cy.get("input[name='otp']").type("123456");
    cy.get("input[name='site-name']").type(
      Math.random().toString(36).substring(7)
    );
    cy.get("input[name='phone']").type("1234567890");
    cy.get("#submit").click();
    cy.contains("processing");
    cy.url().should("include", "/redirect");
    cy.url().should("include", "/app");
  });
});
