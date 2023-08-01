Cypress Testsuite
---

1. delete the existing cypress folder within your frappe application folder.

2. clone this repository in the apps/frappe directory

```bash
$ git clone git@github.com:frappe/cypress-testsuite.git cypress

```

3. create a cypress.json file within the frappe application directory, an example config for it would go as follows:


```json
{
  "baseUrl": "http://<instance-url>:<port>",
  "projectId": "92odwv",
  "adminPassword": "frappe",
  "viewportHeight": 1080,
  "viewportWidth": 1920
}
```

4. checkout the [commands.js](support/commands.js) for available commands, and some [example ui tests](integration/) for guidelines.

