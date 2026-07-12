# Enterprise "Shop" Seed Data — Plan

The Context Engine ingests a single **universal event** contract
(`schemas/event/v1.0.0/event.schema.json`) from every source system. To make
the engine's graph, profiler, and prediction paths light up with recognizable,
realistic behavior, we generate seed data for three archetypal enterprise
buyers — the kind of "shops" you actually find in the field:

| Shop | Tenant | Stack |
| --- | --- | --- |
| **SAP shop** | `globex-industries` | SuccessFactors · S/4HANA · Ariba · Concur |
| **Salesforce shop** | `initech-global` | Sales Cloud · Service Cloud · Marketing Cloud · CPQ · Experience Cloud |
| **Oracle shop** | `umbrella-holdings` | Fusion HCM · Fusion ERP · Fusion SCM · CX · NetSuite |

Each shop is **one tenant**. Within a tenant there are **products** (what the
customer licenses), each product has **modules**, and each module has
**personas** who generate module-specific activity.

## How the domain maps onto the universal schema

Real enterprise suites don't emit one undifferentiated stream — each module has
its own API/connector, its own objects, and its own users. We preserve that
grain:

| Concept | Schema field | Example |
| --- | --- | --- |
| Product + module | `applicationId` (module-grain) | `sap_successfactors_learning` |
| Deployed instance | `applicationInstanceId` | `sf-lms-prod-01` |
| Suite / module labels | `action.metadata.suite` / `.module` | `SAP SuccessFactors` / `Learning` |
| System-native action | `action.type` + `action.category` | `enroll_course` / `create` |
| Business object | `object.objectType` + `object.objectId` | `course` / `LRN-004821` |
| Realistic payload | `object.objectDetails`, `action.metadata` | amounts, statuses, cost centers |
| Persona identity | `actor.nativeUserId` + `actor.userIdType` | `10041288` / `employee_id` |
| Role at time of event | `actor.roles` | `["recruiter"]` |
| Session / trace | `context.sessionId`, `context.correlationId` | groups a workflow |

Using **module-grain `applicationId`** (rather than one id per product) means the
profiler renders a node per module and — crucially — detects **cross-module and
cross-product sequences** (e.g. Ariba requisition → S/4HANA purchase order),
because the sequence detector keys transitions on a change of `applicationId`.

### Identity realism

`actor.userIdType` follows how each product actually issues identity, which also
exercises the engine's identity-resolution across systems:

- **SAP** — `employee_id` for SuccessFactors/S4/HR flows; `email` for Concur.
- **Salesforce** — `sso_subject` (federated SSO is the norm).
- **Oracle** — `employee_id` for HCM/ERP; `email` for CX.

### Timing realism

Events are placed on real calendar cadences so the temporal detectors find
thick edges:

- **daily / weekday** routines (sprint-like operational work, case handling).
- **weekly** routines (Monday approvals, forecast submits).
- **month-end** routines (financial close, expense submission, payroll).
- **cross-app links** fire on a weekly cadence and place their two events inside
  the detector's 30-minute window, recurring well past the 2-occurrence
  threshold, so cross-system workflows surface as high-confidence sequences.

Some routines draw object IDs from a **stable pool** (an AE working the same
opportunities, an agent revisiting the same cases) so the "active objects"
detector — which needs ≥2 interactions in the trailing 14 days — has material.

## Per-shop breakdown

### SAP shop — `globex-industries`

| Product | Modules | Representative personas |
| --- | --- | --- |
| SuccessFactors | Employee Central, Recruiting, Learning, Performance & Goals, Compensation, Workforce Analytics | HR ops specialist, recruiter, hiring manager, learning admin, people manager, comp analyst, HR analyst, employee |
| S/4HANA | Finance (FI), Materials Mgmt (MM), Sales & Distribution (SD) | Financial accountant, AP clerk, procurement specialist, order processor |
| Ariba | Sourcing, Buying, Supplier Management | Sourcing manager, buyer, requisitioner, category manager |
| Concur | Expense, Travel, Invoice | Employee submitter, approving manager, finance auditor, travel arranger, AP processor |

**Cross-app trails:** Recruiting hire → Employee Central onboarding · Ariba
requisition approved → S/4HANA purchase order → goods receipt · Concur travel
request → Concur expense report · SuccessFactors comp change → S/4HANA payroll
posting.

### Salesforce shop — `initech-global`

| Product (Cloud) | Modules | Representative personas |
| --- | --- | --- |
| Sales Cloud | Leads, Opportunities, Forecasting, Accounts | SDR, account executive, sales manager, sales ops |
| Service Cloud | Cases, Knowledge, Omni-Channel | Support agent, support team lead, knowledge manager |
| Marketing Cloud | Journeys, Campaigns | Marketing specialist, campaign manager |
| CPQ | Quotes, Approvals | Deal-desk analyst, sales engineer, deal-desk manager |
| Experience Cloud | Partner Portal, Customer Community | Partner user, self-service customer |

**Cross-cloud trails:** Marketing campaign → Lead created (MQL handoff) · Lead
converted → Opportunity · Opportunity to Proposal → CPQ quote · Case escalated →
Knowledge article linked · Closed-Won → Service onboarding case.

### Oracle shop — `umbrella-holdings`

| Product | Modules | Representative personas |
| --- | --- | --- |
| Fusion HCM | Core HR, Payroll, Talent, Absence, Recruiting | HR specialist, payroll manager, people manager, employee, recruiter |
| Fusion ERP | General Ledger, Payables, Receivables, Expenses | GL accountant, AP specialist, AR analyst, employee |
| Fusion SCM | Procurement, Inventory, Order Management | Buyer, warehouse analyst, order manager |
| CX | Sales, Service | Sales rep, service agent |
| NetSuite | Financials, Order-to-Cash | Controller, billing specialist |

**Cross-app trails:** Procurement PO approved → Payables invoice (procure-to-pay)
· Order Management booked → Receivables receipt → NetSuite billing · Recruiting
offer accepted → Core HR new hire → Payroll setup · Expenses approved → Payables
payment · CX opportunity won → Order Management sales order.

## Deliverables

```
samples/shops/
  framework.py          # Persona/Module/Activity/Routine/CrossAppLink + emitter
  sap.py                # SAP shop definition
  salesforce.py         # Salesforce shop definition
  oracle.py             # Oracle shop definition
  generate.py           # CLI: generate/load one shop or all
  README.md
  data/
    sap_events.json
    salesforce_events.json
    oracle_events.json
tests/test_shop_data.py # schema-validates every event; asserts patterns detected
```

Every generated event is validated against the universal JSON Schema with the
same `SchemaValidator` the ingestion API uses, and the generators are
deterministic (seeded RNG) so the JSON is reproducible.

## Usage

```bash
# Generate all three shops' JSON files
python -m samples.shops.generate generate --shop all

# Or one shop
python -m samples.shops.generate generate --shop sap

# Load a shop into a running engine (batched)
python -m samples.shops.generate load --shop salesforce --base-url http://localhost:8000
```
