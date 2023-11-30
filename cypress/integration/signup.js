context("Signup", () => {
  // open /signup 
  // check if the page is signup
  it("greets with signup screen", () => {
    cy.visit("/signup");
    // title should be signup
    cy.title().should("eq", "Signup");
    // fill the form
    cy.get("input[name='first-name']").type("Test");
    cy.get("input[name='last-name']").type("User");
    cy.get("input[name='email']").type(
      Math.random().toString(36).substring(7) + "@onehash.ai"
    );
    cy.get("input[name='company-name']").type("OneHash");
    // a popuo should have text "hello world"
    cy.get(".modal[role='dialog']").should("contain", "Hello World");
    cy.get("input[name='site-name']").type(
      Math.random().toString(36).substring(7)
    );
    cy.get("input[name='password']").type("Rohit123##");
    // click on signup
    cy.get("input[name='phone'").type("1234567890");
    //cy.get("button[type='submit']").click();
    // click on submit
    cy.get("button[type='submit']").click();
    cy.get("input[name='otp']").type("123456");
    // check if withing 2 minuted , <li> with id step3 has class "is-complete"
    cy.get("#step3", { timeout: 200000 }).should("have.class", "is-complete");
  });
});
