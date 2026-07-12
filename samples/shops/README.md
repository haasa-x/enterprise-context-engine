# Enterprise "Shop" Seed Data

Realistic, multi-application seed data for three archetypal enterprise buyers.
Where [`../data`](../data) models one small fictional company across three apps,
this set models the **full stacks** big enterprises actually run — one tenant per
shop, every product broken into its real modules, every module driven by
role-appropriate personas.

See [`../../SHOP_DATA_PLAN.md`](../../SHOP_DATA_PLAN.md) for the full design.

| Shop | Tenant | Products (→ modules) |
| --- | --- | --- |
| **SAP** | `globex-industries` | SuccessFactors (EC · Recruiting · Learning · Performance · Compensation · Analytics) · S/4HANA (FI · MM · SD) · Ariba (Sourcing · Buying · Supplier) · Concur (Expense · Travel · Invoice) |
| **Salesforce** | `initech-global` | Sales Cloud (Leads · Opportunities · Forecasting · Accounts) · Service Cloud (Cases · Knowledge · Omni) · Marketing Cloud (Journeys · Campaigns) · CPQ (Quotes · Approvals) · Experience Cloud (Partner · Community) |
| **Oracle** | `umbrella-holdings` | Fusion HCM (Core · Payroll · Talent · Absence · Recruiting) · Fusion ERP (GL · AP · AR · Expenses) · Fusion SCM (Procurement · Inventory · Order Mgmt) · CX (Sales · Service) · NetSuite (Financials · O2C) |

Each shop generates ~8k–16k events across ~6 months, ~15 personas, and ~13–16
module-grain applications.

## How modules map to the schema

Each module is a distinct `applicationId` (e.g. `sap_successfactors_learning`),
so the profiler renders a node per module and detects **cross-module and
cross-product sequences**. The human-readable suite and module are also carried
in `action.metadata.suite` / `.module`, and identity type (`actor.userIdType`)
matches how each product issues identity — `employee_id` for SAP/Oracle HR,
`email` for Concur, `sso_subject` for Salesforce.

## Quick start

```bash
# Generate all three shops' JSON files (deterministic)
python -m samples.shops.generate generate --shop all

# Or a single shop
python -m samples.shops.generate generate --shop sap

# Load a shop into a running engine (uses the shop's own tenant id)
docker compose up -d          # from the repo root
python -m samples.shops.generate load --shop salesforce --base-url http://localhost:8000
```

Generated files land in [`data/`](./data): `sap_events.json`,
`salesforce_events.json`, `oracle_events.json`.

## What lights up

- **Per-module action patterns** — daily/weekly/monthly cadences per persona
  (AP clerks posting invoices, recruiters advancing candidates, agents resolving
  cases, controllers closing the books at month-end).
- **Cross-application sequences** — one persona spanning two modules, e.g.
  Ariba requisition → S/4HANA purchase order, Salesforce Opportunity → CPQ quote,
  Oracle CX win → SCM sales order.
- **Active objects** — personas revisiting a stable set of opportunities, cases,
  requisitions, and accounts, so the "currently working on" view is populated.

## Extending

To add a module, product, or persona, edit the relevant shop file
(`sap.py`, `salesforce.py`, `oracle.py`): declare a `Module`, add `Persona`s,
and append `Routine`s (recurring single-module activity) or `CrossAppLink`s
(one persona spanning two modules). The [`framework.py`](./framework.py) emitter
handles schema conformance, identifiers, sessions, and calendar placement.
