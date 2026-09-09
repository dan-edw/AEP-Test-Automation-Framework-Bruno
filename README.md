AEP API Regression Automation --- Bruno + Xray
Overview
This repository contains automated API regression tests for Adobe
Experience Platform (AEP) using Bruno CLI, GitHub Actions, and
Xray Cloud.
The framework is designed so that:
•	Bruno executes the AEP API regression suite.
•	Adobe IMS OAuth authentication is handled automatically at
collection level.
•	Declarative Bruno assertions provide the actual API validation.
•	Each Bruno request maps to an existing Jira/Xray Test using its
CUTECH-xxxx key.
•	Bruno JSON is retained for detailed assertion results.
•	Bruno JUnit is transformed into an Xray-ready report containing one
testcase per Jira/Xray Test.
•	Xray is the source of truth for regression PASS/FAIL results.
•	API test failures do not make the GitHub workflow fail.
•	Pipeline, configuration, report-generation, or Xray integration
failures do fail the workflow.
________________________________________
High-Level Flow
GitHub Actions
      |
      v
Bruno CLI
      |
      +-- Collection-level Adobe OAuth
      |
      +-- AEP API requests
      |
      +-- Declarative assertions
      |
      +-- JUnit report
      |
      +-- Bruno JSON report
              |
              v
      Xray JUnit Filter
              |
              +-- Remove Bruno assertion-generated JUnit rows
              +-- Keep one Jira/Xray mapping testcase per request
              +-- Add Xray test_key
              +-- Apply request PASS/FAIL from declarative assertions
              +-- Validate mappings are complete and unique
              |
              v
        Xray Cloud
              |
              +-- Test Execution
              +-- Existing Tests updated
              +-- PASS / FAIL result
              +-- Detailed Test Run comments
________________________________________
Repository Structure
.github/
└── workflows/
    └── aep-api-regression-bruno.yml

bruno/
├── collections/
│   └── aep-regression/
│       ├── opencollection.yml
│       └── CUTECH-xxxx...request.yml
│
├── manual/
│   └── Request Access Token.request.yml
│
├── environments/
│   ├── dev.json
│   ├── uat.json
│   └── prod.json
│
└── scripts/
    ├── bruno-to-junit.js
    ├── xray-junit-convert.js
    └── xray-junit-filter.py
Exact script placement may vary by branch. The GitHub workflow path
must match the repository structure.
________________________________________
Bruno Collection
The regression collection uses the OpenCollection format.
Example opencollection.yml:
opencollection: 1.0.0

info:
  name: AEP Regression
The collection-level before-request script acquires an Adobe access
token when one is not already available and adds it to each request:
Authorization: Bearer <ACCESS_TOKEN>
Authentication uses the Adobe IMS client-credentials flow.
The required values are supplied by GitHub Actions rather than committed
to the collection.
________________________________________
Environment Variables
The workflow currently supplies the following values to Bruno:
Variable Purpose
________________________________________
AEP_CLIENT_ID Adobe API client ID
AEP_CLIENT_SECRET Adobe API client secret
AEP_SCOPE Adobe IMS OAuth scopes
AEP_IMS_ORG Adobe IMS organisation ID
AEP_SANDBOX_NAME Target AEP sandbox
CONTAINER_ID AEP container, currently tenant
Sensitive values should be stored in GitHub Secrets. Non-sensitive
environment configuration can be stored in GitHub Variables or Bruno
environment files as appropriate.
Do not print access tokens, client secrets, or other credentials to
workflow logs.
________________________________________
Adding a Regression Test
Each automated regression request should have a Jira/Xray Test key in
the request name.
Example:
info:
  name: CUTECH-5000 - Create schema
  type: http
  seq: 6
Assertions
Use Bruno declarative assertions for the actual validation:
runtime:
  assertions:
    - expression: res.status
      operator: eq
      value: "201"

    - expression: res.body
      operator: isJson
Add exactly one mapping test containing the Jira/Xray key:
scripts:
  - type: tests
    code: |-
      test("CUTECH-5000", function () {
        expect(true).to.equal(true);
      });
The mapping test is intentionally an always-pass anchor. The declarative
assertions are the source of truth for the API result.
Important Rules
1.	Use one Jira/Xray key per Bruno regression request.
2.	Use exactly one JavaScript mapping test("CUTECH-xxxx").
3.	Put the real API validation in runtime.assertions.
4.	Do not create multiple mapping tests for the same request.
5.	The approach is HTTP-method agnostic and can be used for GET, POST,
PUT, PATCH, DELETE, and other API requests.
________________________________________
Why the JUnit Report Is Filtered
Bruno creates JUnit testcase rows for both:
•	declarative assertions; and
•	JavaScript test() blocks.
For example, five regression requests containing twelve declarative
assertions produce:
5 mapping tests
+ 12 assertion rows
-------------------
17 raw JUnit testcases
Xray should receive five Tests, not seventeen.
xray-junit-filter.py transforms the raw Bruno report before import.
It:
•	derives the expected Jira/Xray keys independently from
bruno-results.json;
•	removes assertion-generated JUnit testcase rows;
•	keeps only the CUTECH-xxxx mapping testcase for each request;
•	adds the Xray test_key property;
•	determines PASS/FAIL from that request's declarative assertions;
•	treats assertion fail and error statuses as failures;
•	checks for duplicate Jira/Xray keys;
•	checks for missing or unexpected mappings; and
•	verifies the final filtered JUnit matches the Bruno regression
requests.
This means adding another Jira-keyed Bruno request automatically
increases the expected Xray test count. No hardcoded suite count needs
to be maintained.
________________________________________
Reports
Bruno generates two reports during CI:
test-results.xml
JUnit output used as the basis for the Xray import.
The raw report is filtered before it is uploaded to Xray.
bruno-results.json
Structured Bruno execution results used for:
•	per-request assertion status;
•	assertion failure details;
•	request metadata;
•	Xray Test Run comments; and
•	regression summary counts.
________________________________________
Xray Integration
The filtered JUnit report is imported into Xray Cloud.
The import creates a new Test Execution for the CI run and maps
results to the existing Jira/Xray Tests using the test_key property.
Before import, the workflow verifies that test-results.xml exists and
contains at least one testcase.
An Xray import failure is considered an integration failure and makes
the GitHub workflow fail.
Detailed Test Run comments can include:
Automated API Regression Result

Jira Test: CUTECH-xxxx
Bruno Request: <request name>

Result: PASS / FAIL

Request:
GET / POST / ...

HTTP Status: <status>
Duration: <duration> ms

Assertions:
PASS: ...
FAIL: ...

Source: GitHub Actions / Bruno CLI
________________________________________
CI Result Policy
The workflow intentionally separates test failures from pipeline
failures.
________________________________________
Scenario GitHub Actions Xray
________________________________________
All API assertions pass Green PASS
One or more API Green FAIL recorded against
assertions fail affected Tests
Bruno cannot execute / Red Import not trusted
reports are missing
JUnit/Xray mapping Red Import blocked
validation fails
Xray Red Integration failure
authentication/import
fails
This keeps Xray as the source of truth for regression results, while
GitHub Actions reports whether the automation pipeline itself executed
successfully.
________________________________________
Running in GitHub Actions
The workflow runs Bruno directly and captures the Bruno exit code
without allowing normal API assertion failures to make the regression
step red.
The workflow still validates that the required output reports were
generated.
Typical execution sequence:
Resolve environment
        ↓
Run Bruno regression
        ↓
Generate JUnit + JSON
        ↓
Copy/prepare reports
        ↓
Filter and validate JUnit
        ↓
Authenticate to Xray
        ↓
Import JUnit
        ↓
Update Xray Test Run details
        ↓
Publish execution summary
________________________________________
Expected Regression Summary
A run with five Test Cases and twelve assertions, where three requests
each contain a failed assertion, would be represented as:
Test Cases
Total:  5
Passed: 2
Failed: 3

Assertions
Total:  12
Passed: 9
Failed: 3
The raw Bruno JUnit testcase count may be higher because Bruno emits
individual declarative assertions as JUnit testcase rows. Always use the
filtered Xray report or Bruno JSON when interpreting regression-level
results.
________________________________________
Adding More Coverage
To add a new API regression test:
1.	Create the Bruno request in the regression collection.
2.	Include its existing Jira/Xray key in the request name.
3.	Add the required declarative assertions.
4.	Add one always-pass Jira/Xray mapping test.
5.	Add any required environment variables or test data.
6.	Run the workflow and confirm the Test appears in the new Xray Test
Execution.
7.	Confirm the Xray Test Run contains the expected PASS/FAIL result and
assertion details.
No workflow test-count change should be required when new Jira-keyed
requests are added.
________________________________________
Current Status
The framework currently supports:
•	Bruno CLI execution in GitHub Actions;
•	AEP Adobe IMS OAuth client-credentials authentication;
•	multiple independent API regression tests;
•	declarative assertion validation;
•	JUnit and structured JSON reporting;
•	automatic Jira/Xray Test mapping;
•	dynamic Xray testcase-count validation;
•	existing Xray Test updates;
•	independent PASS/FAIL outcomes;
•	detailed assertion failure reporting; and
•	GitHub-green / Xray-source-of-truth handling for API regression
failures.
Further testing can expand API coverage and validate the framework
across additional request types, environments, negative scenarios, and
failure conditions.