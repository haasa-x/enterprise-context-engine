"""SAP shop — a Globex Industries tenant running the full SAP enterprise stack.

Products: SuccessFactors (HCM suite), S/4HANA (ERP), Ariba (procurement), and
Concur (travel & expense). Each product is broken into the modules a real
customer would run, each driven by role-appropriate personas.
"""

from __future__ import annotations

import random
from typing import Any

from samples.shops.framework import (
    Activity,
    CrossAppLink,
    Module,
    Persona,
    Routine,
    Shop,
    Step,
    money,
    pick,
)

# ---------------------------------------------------------------------------
# Modules (module-grain applications)
# ---------------------------------------------------------------------------

_SF_CONNECTOR = "successfactors-odata-connector"
_SF_VERSION = "2.3.1"

SF_EMPLOYEE_CENTRAL = Module(
    "sap_successfactors_ec", "sf-ec-prod-01", _SF_CONNECTOR, _SF_VERSION,
    "SAP SuccessFactors", "Employee Central",
)
SF_RECRUITING = Module(
    "sap_successfactors_rcm", "sf-rcm-prod-01", _SF_CONNECTOR, _SF_VERSION,
    "SAP SuccessFactors", "Recruiting",
)
SF_LEARNING = Module(
    "sap_successfactors_lms", "sf-lms-prod-01", _SF_CONNECTOR, _SF_VERSION,
    "SAP SuccessFactors", "Learning",
)
SF_PERFORMANCE = Module(
    "sap_successfactors_pmgm", "sf-pmgm-prod-01", _SF_CONNECTOR, _SF_VERSION,
    "SAP SuccessFactors", "Performance & Goals",
)
SF_COMPENSATION = Module(
    "sap_successfactors_comp", "sf-comp-prod-01", _SF_CONNECTOR, _SF_VERSION,
    "SAP SuccessFactors", "Compensation",
)
SF_ANALYTICS = Module(
    "sap_successfactors_wfa", "sf-wfa-prod-01", _SF_CONNECTOR, _SF_VERSION,
    "SAP SuccessFactors", "Workforce Analytics",
)

_S4_CONNECTOR = "s4hana-cloud-connector"
_S4_VERSION = "3.0.4"

S4_FINANCE = Module(
    "sap_s4hana_fi", "s4-fi-prod-01", _S4_CONNECTOR, _S4_VERSION,
    "SAP S/4HANA", "Finance",
)
S4_MATERIALS = Module(
    "sap_s4hana_mm", "s4-mm-prod-01", _S4_CONNECTOR, _S4_VERSION,
    "SAP S/4HANA", "Materials Management",
)
S4_SALES = Module(
    "sap_s4hana_sd", "s4-sd-prod-01", _S4_CONNECTOR, _S4_VERSION,
    "SAP S/4HANA", "Sales & Distribution",
)

_ARIBA_CONNECTOR = "ariba-api-connector"
_ARIBA_VERSION = "1.8.2"

ARIBA_SOURCING = Module(
    "sap_ariba_sourcing", "ariba-src-prod-01", _ARIBA_CONNECTOR, _ARIBA_VERSION,
    "SAP Ariba", "Sourcing",
)
ARIBA_BUYING = Module(
    "sap_ariba_buying", "ariba-buy-prod-01", _ARIBA_CONNECTOR, _ARIBA_VERSION,
    "SAP Ariba", "Buying",
)
ARIBA_SUPPLIER = Module(
    "sap_ariba_slp", "ariba-slp-prod-01", _ARIBA_CONNECTOR, _ARIBA_VERSION,
    "SAP Ariba", "Supplier Management",
)

_CONCUR_CONNECTOR = "concur-connector"
_CONCUR_VERSION = "1.5.0"

CONCUR_EXPENSE = Module(
    "sap_concur_expense", "concur-exp-prod-01", _CONCUR_CONNECTOR, _CONCUR_VERSION,
    "SAP Concur", "Expense",
)
CONCUR_TRAVEL = Module(
    "sap_concur_travel", "concur-trv-prod-01", _CONCUR_CONNECTOR, _CONCUR_VERSION,
    "SAP Concur", "Travel",
)
CONCUR_INVOICE = Module(
    "sap_concur_invoice", "concur-inv-prod-01", _CONCUR_CONNECTOR, _CONCUR_VERSION,
    "SAP Concur", "Invoice",
)

# ---------------------------------------------------------------------------
# Personas — SAP HR/ERP uses employee_id; Concur uses email
# ---------------------------------------------------------------------------

HR_SPECIALIST = Persona("10041288", "Priya Nair", ("hr_ops_specialist",), "employee_id")
RECRUITER = Persona("10052910", "Marcus Feld", ("recruiter",), "employee_id")
HIRING_MANAGER = Persona(
    "10033471", "Dana Rowe", ("hiring_manager", "people_manager"), "employee_id")
LEARNING_ADMIN = Persona("10061205", "Sofia Bianchi", ("learning_admin",), "employee_id")
PEOPLE_MANAGER = Persona("10029833", "Tomás Vela", ("people_manager",), "employee_id")
COMP_ANALYST = Persona("10047762", "Grace Okoro", ("compensation_analyst",), "employee_id")
HR_ANALYST = Persona("10055018", "Ken Ishida", ("workforce_analyst",), "employee_id")
EMPLOYEE = Persona("10071940", "Lena Fischer", ("employee",), "employee_id")

FIN_ACCOUNTANT = Persona("10012004", "Raj Malhotra", ("financial_accountant",), "employee_id")
AP_CLERK = Persona("10012455", "Nadia Haddad", ("accounts_payable_clerk",), "employee_id")
PROCUREMENT_SPEC = Persona("10013890", "Owen Pierce", ("procurement_specialist",), "employee_id")
ORDER_PROCESSOR = Persona("10014377", "Mei Lin", ("order_processor",), "employee_id")

SOURCING_MANAGER = Persona("10015120", "Diego Santos", ("sourcing_manager",), "employee_id")
BUYER = Persona("10015661", "Hannah Volk", ("buyer",), "employee_id")
CATEGORY_MANAGER = Persona("10016043", "Ivan Petrov", ("category_manager",), "employee_id")

EXP_SUBMITTER = Persona("lena.fischer@globex.example", "Lena Fischer", ("employee",), "email")
EXP_APPROVER = Persona("tomas.vela@globex.example", "Tomás Vela", ("people_manager",), "email")
FIN_AUDITOR = Persona("dana.reyes@globex.example", "Dana Reyes", ("finance_auditor",), "email")
TRAVEL_ARRANGER = Persona("carol.diaz@globex.example", "Carol Diaz", ("travel_arranger",), "email")
AP_PROCESSOR = Persona("nadia.haddad@globex.example", "Nadia Haddad", ("ap_processor",), "email")

# Stable object pools so "active objects" have recurring interactions.
_OPEN_REQUISITIONS = ("REQ-2026-0480", "REQ-2026-0491", "REQ-2026-0507", "REQ-2026-0512")
_CLOSE_TASKS = ("CLOSE-FY26-GL", "CLOSE-FY26-AP", "CLOSE-FY26-AR", "CLOSE-FY26-FX")
_KEY_SUPPLIERS = ("SUP-100234", "SUP-100251", "SUP-100288")


# ---------------------------------------------------------------------------
# Detail generators
# ---------------------------------------------------------------------------


def _leave_details(rng: random.Random) -> dict[str, Any]:
    return {"leave_type": pick(rng, "annual", "sick", "parental", "unpaid"),
            "days": rng.randint(1, 10)}


def _course_details(rng: random.Random) -> dict[str, Any]:
    return {"course": pick(rng, "Data Privacy 2026", "Anti-Bribery", "Leadership 201",
                           "SAP Fiori Basics", "Workplace Safety"),
            "delivery": pick(rng, "online", "instructor_led", "virtual")}


def _po_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 1500, 240000, "EUR"),
            "plant": pick(rng, "1010", "1710", "2020"),
            "material_group": pick(rng, "MRO", "RAW", "SERV", "IT-HW")}


def _journal_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 5000, 900000, "EUR"),
            "ledger": "0L", "document_type": pick(rng, "SA", "KR", "DR"),
            "company_code": pick(rng, "1000", "2000", "3000")}


def _sourcing_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 50000, 3500000, "EUR"),
            "commodity": pick(rng, "Logistics", "IT Services", "Packaging", "Facilities"),
            "region": pick(rng, "EMEA", "AMER", "APAC")}


def _expense_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 45, 4200),
            "expense_type": pick(rng, "airfare", "lodging", "meals", "ground_transport"),
            "cost_center": pick(rng, "CC-4100", "CC-4200", "CC-5300"),
            "line_items": rng.randint(2, 16)}


def _trip_details(rng: random.Random) -> dict[str, Any]:
    return {"origin": pick(rng, "FRA", "LHR", "JFK", "SIN"),
            "destination": pick(rng, "SFO", "BLR", "DXB", "SYD"),
            "cabin": pick(rng, "economy", "premium_economy", "business")}


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

_ROUTINES: tuple[Routine, ...] = (
    # SuccessFactors — Employee Central
    Routine(
        SF_EMPLOYEE_CENTRAL, (HR_SPECIALIST,), "weekday", 9,
        (
            Activity("view_employee_profile", "read", "employee_record", "EMP-"),
            Activity("update_personal_info", "update", "employee_record", "EMP-",
                     metadata=lambda r: {"field": pick(r, "address", "bank", "dependent")}),
        ),
        occurrences=(2, 4),
    ),
    Routine(
        SF_EMPLOYEE_CENTRAL, (EMPLOYEE,), "weekly", 8,
        (Activity("submit_time_off", "create", "leave_request", "LR-", details=_leave_details),),
    ),
    Routine(
        SF_EMPLOYEE_CENTRAL, (PEOPLE_MANAGER,), "weekly", 9,
        (Activity("approve_time_off", "approve", "leave_request", "LR-",
                  details=_leave_details),),
        occurrences=(2, 5), device_mix=("desktop", "mobile"),
    ),
    # SuccessFactors — Recruiting
    Routine(
        SF_RECRUITING, (RECRUITER,), "weekday", 10,
        (
            Activity("screen_candidate", "read", "candidate", "CAND-"),
            Activity("advance_candidate_stage", "update", "candidate", "CAND-",
                     metadata=lambda r: {"to_stage": pick(r, "phone_screen", "onsite", "offer")}),
        ),
        occurrences=(2, 5),
    ),
    Routine(
        SF_RECRUITING, (HIRING_MANAGER,), "weekly", 11,
        (Activity("create_job_requisition", "create", "job_requisition", "JR-",
                  metadata=lambda r: {"headcount": r.randint(1, 3),
                                      "level": pick(r, "IC3", "IC4", "M1")}),),
    ),
    # SuccessFactors — Learning
    Routine(
        SF_LEARNING, (EMPLOYEE, PEOPLE_MANAGER), "weekly", 14,
        (
            Activity("launch_content", "read", "course", "LRN-", id_pool=(
                "LRN-000481", "LRN-000492", "LRN-000513"), details=_course_details),
            Activity("complete_course", "update", "course", "LRN-", details=_course_details),
        ),
    ),
    Routine(
        SF_LEARNING, (LEARNING_ADMIN,), "weekday", 9,
        (Activity("assign_learning", "create", "learning_assignment", "LA-",
                  metadata=lambda r: {"assignees": r.randint(3, 60),
                                      "curriculum": pick(r, "compliance", "onboarding",
                                                         "leadership")}),),
    ),
    # SuccessFactors — Performance & Goals
    Routine(
        SF_PERFORMANCE, (PEOPLE_MANAGER,), "weekly", 15,
        (
            Activity("write_review", "update", "performance_review", "PR-"),
            Activity("submit_feedback", "create", "feedback", "FB-"),
        ),
    ),
    Routine(
        SF_PERFORMANCE, (EMPLOYEE,), "weekly", 16,
        (Activity("set_goal", "create", "goal", "GOAL-",
                  metadata=lambda r: {"category": pick(r, "delivery", "growth", "impact")}),),
    ),
    # SuccessFactors — Compensation
    Routine(
        SF_COMPENSATION, (COMP_ANALYST,), "monthly_end", 10,
        (
            Activity("model_comp_plan", "read", "comp_plan", "CP-"),
            Activity("submit_merit_increase", "create", "comp_worksheet", "CW-",
                     details=lambda r: {**money(r, 2000, 25000), "merit_pct": round(
                         r.uniform(1.5, 6.0), 1)}),
        ),
        occurrences=(3, 8),
    ),
    # SuccessFactors — Workforce Analytics
    Routine(
        SF_ANALYTICS, (HR_ANALYST,), "weekly", 8,
        (Activity("run_headcount_report", "read", "report", "RPT-", id_pool=(
            "RPT-HEADCOUNT", "RPT-ATTRITION", "RPT-DIVERSITY"),
            metadata=lambda r: {"dimension": pick(r, "region", "function", "band")}),),
        occurrences=(1, 2),
    ),
    # S/4HANA — Finance
    Routine(
        S4_FINANCE, (FIN_ACCOUNTANT,), "weekday", 9,
        (Activity("post_journal_entry", "create", "journal_entry", "JE-",
                  details=_journal_details),),
        occurrences=(3, 9),
    ),
    Routine(
        S4_FINANCE, (FIN_ACCOUNTANT, AP_CLERK), "monthly_end", 11,
        (Activity("run_financial_close", "update", "close_task", "CLOSE-",
                  id_pool=_CLOSE_TASKS,
                  metadata=lambda r: {"status": pick(r, "in_progress", "completed")}),),
        occurrences=(2, 4),
    ),
    # S/4HANA — Materials Management
    Routine(
        S4_MATERIALS, (PROCUREMENT_SPEC,), "weekday", 10,
        (
            Activity("create_purchase_order", "create", "purchase_order", "PO-45",
                     details=_po_details),
            Activity("post_goods_receipt", "update", "goods_receipt", "GR-50"),
        ),
        occurrences=(2, 6),
    ),
    # S/4HANA — Sales & Distribution
    Routine(
        S4_SALES, (ORDER_PROCESSOR,), "weekday", 11,
        (
            Activity("create_sales_order", "create", "sales_order", "SO-",
                     details=lambda r: money(r, 800, 180000, "EUR")),
            Activity("create_delivery", "create", "delivery", "DLV-80"),
        ),
        occurrences=(3, 8),
    ),
    # Ariba — Sourcing
    Routine(
        ARIBA_SOURCING, (SOURCING_MANAGER,), "weekly", 10,
        (
            Activity("create_sourcing_event", "create", "sourcing_event", "RFX-",
                     details=_sourcing_details),
            Activity("award_supplier", "approve", "sourcing_event", "RFX-",
                     metadata=lambda r: {"suppliers_invited": r.randint(3, 9)}),
        ),
    ),
    # Ariba — Buying
    Routine(
        ARIBA_BUYING, (BUYER,), "weekday", 9,
        (
            Activity("create_requisition", "create", "requisition", "REQ-2026-",
                     id_pool=_OPEN_REQUISITIONS, details=lambda r: money(r, 200, 45000, "EUR")),
            Activity("approve_requisition", "approve", "requisition", "REQ-2026-",
                     id_pool=_OPEN_REQUISITIONS),
        ),
        occurrences=(1, 3), device_mix=("desktop", "mobile"),
    ),
    # Ariba — Supplier Management
    Routine(
        ARIBA_SUPPLIER, (CATEGORY_MANAGER,), "weekly", 13,
        (Activity("assess_supplier_risk", "read", "supplier", "SUP-", id_pool=_KEY_SUPPLIERS,
                  metadata=lambda r: {"risk_tier": pick(r, "low", "medium", "high")}),),
        occurrences=(2, 4),
    ),
    # Concur — Expense
    Routine(
        CONCUR_EXPENSE, (EXP_SUBMITTER,), "monthly_end", 16,
        (
            Activity("create_expense_report", "create", "expense_report", "EXP-",
                     details=_expense_details),
            Activity("submit_expense_report", "update", "expense_report", "EXP-"),
        ),
    ),
    Routine(
        CONCUR_EXPENSE, (EXP_APPROVER,), "weekly", 9,
        (Activity("approve_expense_report", "approve", "expense_report", "EXP-",
                  details=_expense_details),),
        occurrences=(2, 5), device_mix=("desktop", "mobile", "mobile"),
    ),
    Routine(
        CONCUR_EXPENSE, (FIN_AUDITOR,), "weekly", 14,
        (Activity("audit_expense_report", "read", "expense_report", "EXP-",
                  metadata=lambda r: {"flagged": pick(r, "none", "policy", "receipt_missing")}),),
        occurrences=(3, 7),
    ),
    # Concur — Travel
    Routine(
        CONCUR_TRAVEL, (TRAVEL_ARRANGER,), "weekday", 10,
        (Activity("book_flight", "create", "trip", "TRIP-", details=_trip_details),),
        occurrences=(1, 3),
    ),
    # Concur — Invoice
    Routine(
        CONCUR_INVOICE, (AP_PROCESSOR,), "weekday", 13,
        (
            Activity("process_vendor_invoice", "create", "vendor_invoice", "VINV-",
                     details=lambda r: money(r, 300, 90000)),
            Activity("match_invoice_po", "update", "vendor_invoice", "VINV-",
                     metadata=lambda r: {"match": pick(r, "2-way", "3-way")}),
        ),
        occurrences=(2, 6),
    ),
)


# ---------------------------------------------------------------------------
# Cross-application workflows
# ---------------------------------------------------------------------------

# Each link is one persona spanning two modules end-to-end — the shape the
# profiler surfaces as a cross-app sequence. Evening hours keep the pair
# isolated from the day's routines.
_CROSS_APP: tuple[CrossAppLink, ...] = (
    # A traveler books the trip, then files the matching expense report.
    CrossAppLink(
        "travel_to_expense", EXP_SUBMITTER,
        Step(CONCUR_TRAVEL, "create_travel_request", "create", "trip", "TRIP-",
             details=_trip_details),
        Step(CONCUR_EXPENSE, "create_expense_report", "create", "expense_report", "EXP-",
             details=_expense_details),
        hour=18, probability=0.85,
    ),
    # A procurement specialist releases the Ariba requisition, then raises the
    # S/4HANA purchase order for it.
    CrossAppLink(
        "requisition_to_po", PROCUREMENT_SPEC,
        Step(ARIBA_BUYING, "release_requisition", "approve", "requisition", "REQ-2026-",
             details=lambda r: money(r, 500, 60000, "EUR")),
        Step(S4_MATERIALS, "create_purchase_order", "create", "purchase_order", "PO-45",
             details=_po_details),
        hour=18, probability=0.85,
    ),
    # A recruiter marks the candidate hired, then opens their Employee Central record.
    CrossAppLink(
        "recruit_to_onboard", RECRUITER,
        Step(SF_RECRUITING, "mark_candidate_hired", "update", "candidate", "CAND-"),
        Step(SF_EMPLOYEE_CENTRAL, "create_new_hire", "create", "employee_record", "EMP-"),
        hour=19, probability=0.7,
    ),
    # An AP processor clears the Concur invoice, then posts the S/4HANA FI journal.
    CrossAppLink(
        "invoice_to_journal", AP_PROCESSOR,
        Step(CONCUR_INVOICE, "post_vendor_invoice", "update", "vendor_invoice", "VINV-",
             details=lambda r: money(r, 300, 90000)),
        Step(S4_FINANCE, "post_journal_entry", "create", "journal_entry", "JE-",
             details=_journal_details),
        hour=19, probability=0.8,
    ),
)

SHOP = Shop(
    key="sap",
    tenant_id="globex-industries",
    display_name="Globex Industries (SAP shop)",
    routines=_ROUTINES,
    cross_app=_CROSS_APP,
    country="DE",
    region="HE",
)
