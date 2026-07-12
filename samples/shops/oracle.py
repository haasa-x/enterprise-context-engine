"""Oracle shop — an Umbrella Holdings tenant running the Oracle enterprise stack.

Products: Oracle Fusion Cloud HCM, Fusion Cloud ERP (Financials), Fusion Cloud
SCM, Oracle CX, and NetSuite. Each is broken into the modules a real customer
would run. Oracle HCM/ERP identify workers by ``employee_id``; CX uses email.
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
# Modules
# ---------------------------------------------------------------------------

_HCM_CONN = "oracle-fusion-hcm-connector"
_ERP_CONN = "oracle-fusion-erp-connector"
_SCM_CONN = "oracle-fusion-scm-connector"
_HCM_V = "22.4.1"
_ERP_V = "22.4.1"

HCM_CORE = Module(
    "oracle_hcm_core", "hcm-prod", _HCM_CONN, _HCM_V, "Oracle Fusion HCM", "Core HR")
HCM_PAYROLL = Module(
    "oracle_hcm_payroll", "hcm-prod", _HCM_CONN, _HCM_V, "Oracle Fusion HCM", "Payroll")
HCM_TALENT = Module(
    "oracle_hcm_talent", "hcm-prod", _HCM_CONN, _HCM_V, "Oracle Fusion HCM", "Talent Management")
HCM_ABSENCE = Module(
    "oracle_hcm_absence", "hcm-prod", _HCM_CONN, _HCM_V, "Oracle Fusion HCM", "Absence Management")
HCM_RECRUITING = Module(
    "oracle_hcm_recruiting", "hcm-prod", _HCM_CONN, _HCM_V, "Oracle Fusion HCM", "Recruiting")

ERP_GL = Module(
    "oracle_erp_gl", "erp-prod", _ERP_CONN, _ERP_V, "Oracle Fusion ERP", "General Ledger")
ERP_PAYABLES = Module(
    "oracle_erp_ap", "erp-prod", _ERP_CONN, _ERP_V, "Oracle Fusion ERP", "Payables")
ERP_RECEIVABLES = Module(
    "oracle_erp_ar", "erp-prod", _ERP_CONN, _ERP_V, "Oracle Fusion ERP", "Receivables")
ERP_EXPENSES = Module(
    "oracle_erp_expenses", "erp-prod", _ERP_CONN, _ERP_V, "Oracle Fusion ERP", "Expenses")

SCM_PROCUREMENT = Module(
    "oracle_scm_procurement", "scm-prod", _SCM_CONN, "22.4.0", "Oracle Fusion SCM", "Procurement")
SCM_INVENTORY = Module(
    "oracle_scm_inventory", "scm-prod", _SCM_CONN, "22.4.0", "Oracle Fusion SCM", "Inventory")
SCM_ORDER_MGMT = Module(
    "oracle_scm_order_mgmt", "scm-prod", _SCM_CONN, "22.4.0", "Oracle Fusion SCM",
    "Order Management")

CX_SALES = Module(
    "oracle_cx_sales", "cx-prod", "oracle-cx-connector", "21.2.0", "Oracle CX", "Sales")
CX_SERVICE = Module(
    "oracle_cx_service", "cx-prod", "oracle-cx-connector", "21.2.0", "Oracle CX", "Service")

NS_FINANCIALS = Module(
    "oracle_netsuite_financials", "ns-prod", "netsuite-suitetalk-connector", "2024.1",
    "Oracle NetSuite", "Financials")
NS_ORDER_TO_CASH = Module(
    "oracle_netsuite_o2c", "ns-prod", "netsuite-suitetalk-connector", "2024.1",
    "Oracle NetSuite", "Order-to-Cash")

# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

_EID = "employee_id"

HR_SPECIALIST = Persona("300000042118", "Ana Duarte", ("hr_specialist",), _EID)
PAYROLL_MANAGER = Persona("300000042205", "Victor Osei", ("payroll_manager",), _EID)
PEOPLE_MANAGER = Persona("300000042330", "Sara Lindqvist", ("people_manager",), _EID)
EMPLOYEE = Persona("300000042471", "Hiro Tanaka", ("employee",), _EID)
ORC_RECRUITER = Persona("300000042588", "Farah Nasser", ("recruiter",), _EID)

GL_ACCOUNTANT = Persona("300000051004", "Paul Nguyen", ("gl_accountant",), _EID)
AP_SPECIALIST = Persona("300000051188", "Rita Gomez", ("ap_specialist",), _EID)
AR_ANALYST = Persona("300000051245", "Kwame Mensah", ("ar_analyst",), _EID)

BUYER = Persona("300000061077", "Elena Volkova", ("buyer",), _EID)
WAREHOUSE_ANALYST = Persona("300000061152", "Tariq Aziz", ("inventory_analyst",), _EID)
ORDER_MANAGER = Persona("300000061390", "Julia Fernandez", ("order_manager",), _EID)

SALES_REP = Persona("gwen.park@umbrella.example", "Gwen Park", ("sales_rep",), "email")
SERVICE_AGENT = Persona("omar.saleh@umbrella.example", "Omar Saleh", ("service_agent",), "email")

CONTROLLER = Persona("300000071011", "Maya Kaplan", ("controller",), _EID)
BILLING_SPECIALIST = Persona("300000071204", "Leon Wright", ("billing_specialist",), _EID)

# Stable object pools.
_ACCT_PERIODS = ("APR-2026", "MAY-2026", "JUN-2026")
_KEY_SUPPLIERS = ("SUP-70012", "SUP-70045", "SUP-70081")
_OPEN_ORDERS = ("SO-880122", "SO-880155", "SO-880190", "SO-880210")


# ---------------------------------------------------------------------------
# Detail generators
# ---------------------------------------------------------------------------


def _journal_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 4000, 850000), "ledger": "US Primary",
            "period": pick(rng, *_ACCT_PERIODS),
            "source": pick(rng, "Manual", "Payables", "Receivables", "Assets")}


def _invoice_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 250, 120000), "terms": pick(rng, "Net 30", "Net 45", "Net 60"),
            "supplier": pick(rng, *_KEY_SUPPLIERS)}


def _payroll_details(rng: random.Random) -> dict[str, Any]:
    return {"pay_group": pick(rng, "US-Salaried", "US-Hourly", "UK-Salaried"),
            "employees": rng.randint(80, 1400),
            **money(rng, 400000, 6500000)}


def _expense_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 40, 3800), "type": pick(rng, "airfare", "lodging", "meals", "mileage"),
            "cost_center": pick(rng, "CC-1001", "CC-1002", "CC-2005")}


def _po_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 800, 320000), "supplier": pick(rng, *_KEY_SUPPLIERS),
            "category": pick(rng, "IT", "Facilities", "Raw Materials", "Services")}


def _order_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 1200, 260000), "channel": pick(rng, "direct", "partner", "web"),
            "ship_from": pick(rng, "WH-EAST", "WH-WEST", "WH-CENTRAL")}


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

_ROUTINES: tuple[Routine, ...] = (
    # HCM — Core HR
    Routine(
        HCM_CORE, (HR_SPECIALIST,), "weekday", 9,
        (
            Activity("update_worker_assignment", "update", "worker", "WKR-"),
            Activity("process_promotion", "update", "worker", "WKR-",
                     metadata=lambda r: {"grade_to": pick(r, "G6", "G7", "M2")}),
        ),
        occurrences=(1, 4),
    ),
    # HCM — Payroll
    Routine(
        HCM_PAYROLL, (PAYROLL_MANAGER,), "monthly_end", 8,
        (
            Activity("run_payroll", "create", "payroll_run", "PAY-", details=_payroll_details),
            Activity("verify_payroll", "approve", "payroll_run", "PAY-"),
        ),
    ),
    # HCM — Talent
    Routine(
        HCM_TALENT, (PEOPLE_MANAGER,), "weekly", 15,
        (
            Activity("complete_check_in", "create", "check_in", "CHK-"),
            Activity("create_performance_goal", "create", "goal", "GOAL-",
                     metadata=lambda r: {"weight": r.randint(10, 40)}),
        ),
    ),
    # HCM — Absence
    Routine(
        HCM_ABSENCE, (EMPLOYEE,), "weekly", 8,
        (Activity("record_absence", "create", "absence", "ABS-",
                  details=lambda r: {"type": pick(r, "vacation", "sick", "personal"),
                                     "days": r.randint(1, 8)}),),
    ),
    Routine(
        HCM_ABSENCE, (PEOPLE_MANAGER,), "weekly", 9,
        (Activity("approve_absence", "approve", "absence", "ABS-"),),
        occurrences=(2, 5), device_mix=("desktop", "mobile"),
    ),
    # HCM — Recruiting
    Routine(
        HCM_RECRUITING, (ORC_RECRUITER,), "weekday", 10,
        (
            Activity("move_candidate", "update", "candidate", "CAND-",
                     metadata=lambda r: {"phase": pick(r, "screen", "interview", "offer")}),
            Activity("post_requisition", "create", "requisition", "HREQ-"),
        ),
        occurrences=(1, 4),
    ),
    # ERP — General Ledger
    Routine(
        ERP_GL, (GL_ACCOUNTANT,), "weekday", 9,
        (
            Activity("create_journal", "create", "journal", "JRN-", details=_journal_details),
            Activity("post_journal", "update", "journal", "JRN-"),
        ),
        occurrences=(2, 7),
    ),
    Routine(
        ERP_GL, (GL_ACCOUNTANT, CONTROLLER), "monthly_end", 12,
        (Activity("close_period", "update", "accounting_period", "PERIOD-", id_pool=_ACCT_PERIODS,
                  metadata=lambda r: {"status": pick(r, "open", "closed", "adjusting")}),),
        occurrences=(1, 3),
    ),
    # ERP — Payables
    Routine(
        ERP_PAYABLES, (AP_SPECIALIST,), "weekday", 10,
        (
            Activity("enter_invoice", "create", "invoice", "AP-", details=_invoice_details),
            Activity("validate_invoice", "update", "invoice", "AP-",
                     metadata=lambda r: {"hold": pick(r, "none", "price", "quantity")}),
        ),
        occurrences=(3, 9),
    ),
    # ERP — Receivables
    Routine(
        ERP_RECEIVABLES, (AR_ANALYST,), "weekday", 11,
        (
            Activity("create_receipt", "create", "receipt", "RCT-",
                     details=lambda r: money(r, 300, 180000)),
            Activity("apply_receipt", "update", "receipt", "RCT-"),
        ),
        occurrences=(2, 6),
    ),
    # ERP — Expenses
    Routine(
        ERP_EXPENSES, (EMPLOYEE,), "monthly_end", 16,
        (
            Activity("create_expense_report", "create", "expense_report", "EXP-",
                     details=_expense_details),
            Activity("submit_expense_report", "update", "expense_report", "EXP-"),
        ),
    ),
    # SCM — Procurement
    Routine(
        SCM_PROCUREMENT, (BUYER,), "weekday", 9,
        (
            Activity("create_purchase_order", "create", "purchase_order", "SCMPO-",
                     details=_po_details),
            Activity("approve_po", "approve", "purchase_order", "SCMPO-"),
        ),
        occurrences=(2, 6), device_mix=("desktop", "mobile"),
    ),
    # SCM — Inventory
    Routine(
        SCM_INVENTORY, (WAREHOUSE_ANALYST,), "weekday", 8,
        (
            Activity("record_receipt", "create", "inventory_transaction", "INVTXN-"),
            Activity("cycle_count", "update", "inventory_transaction", "INVTXN-",
                     metadata=lambda r: {"variance_pct": round(r.uniform(-3, 3), 2)}),
        ),
        occurrences=(3, 8),
    ),
    # SCM — Order Management
    Routine(
        SCM_ORDER_MGMT, (ORDER_MANAGER,), "weekday", 10,
        (
            Activity("create_sales_order", "create", "sales_order", "SO-", id_pool=_OPEN_ORDERS,
                     details=_order_details),
            Activity("book_order", "update", "sales_order", "SO-", id_pool=_OPEN_ORDERS),
            Activity("schedule_shipment", "update", "shipment", "SHP-"),
        ),
        occurrences=(2, 5),
    ),
    # CX — Sales
    Routine(
        CX_SALES, (SALES_REP,), "weekday", 9,
        (
            Activity("update_opportunity", "update", "opportunity", "CXOPP-",
                     details=lambda r: {**money(r, 5000, 500000),
                                        "stage": pick(r, "Qualify", "Propose", "Win", "Lose")}),
            Activity("create_lead", "create", "lead", "CXLEAD-"),
        ),
        occurrences=(2, 6), device_mix=("desktop", "mobile"),
    ),
    # CX — Service
    Routine(
        CX_SERVICE, (SERVICE_AGENT,), "weekday", 10,
        (
            Activity("create_service_request", "create", "service_request", "SR-",
                     metadata=lambda r: {"severity": pick(r, "1", "2", "3", "4")}),
            Activity("resolve_service_request", "update", "service_request", "SR-"),
        ),
        occurrences=(4, 10),
    ),
    # NetSuite — Financials
    Routine(
        NS_FINANCIALS, (CONTROLLER,), "monthly_end", 13,
        (Activity("close_books", "update", "accounting_period", "NSPERIOD-", id_pool=_ACCT_PERIODS,
                  metadata=lambda r: {"subsidiary": pick(r, "US", "UK", "APAC")}),),
        occurrences=(1, 2),
    ),
    # NetSuite — Order-to-Cash
    Routine(
        NS_ORDER_TO_CASH, (BILLING_SPECIALIST,), "weekday", 11,
        (
            Activity("create_invoice", "create", "invoice", "NSINV-",
                     details=lambda r: money(r, 500, 240000)),
            Activity("apply_payment", "update", "payment", "NSPMT-"),
        ),
        occurrences=(2, 7),
    ),
)


# ---------------------------------------------------------------------------
# Cross-application workflows
# ---------------------------------------------------------------------------

# Single-persona cross-module flows, isolated in the evening so each surfaces as
# one clean cross-app sequence in the profile.
_CROSS_APP: tuple[CrossAppLink, ...] = (
    # An AR analyst records the customer receipt in ERP, then mirrors the
    # invoice into NetSuite (procure/bill reconciliation).
    CrossAppLink(
        "receivable_to_netsuite", AR_ANALYST,
        Step(ERP_RECEIVABLES, "invoice_customer", "create", "receipt", "RCT-",
             details=lambda r: money(r, 500, 200000)),
        Step(NS_ORDER_TO_CASH, "create_invoice", "create", "invoice", "NSINV-",
             details=lambda r: money(r, 500, 240000)),
        hour=18, probability=0.7,
    ),
    # A GL accountant posts the period journal, then closes the books in NetSuite.
    CrossAppLink(
        "gl_to_netsuite_close", GL_ACCOUNTANT,
        Step(ERP_GL, "finalize_period_journal", "update", "journal", "JRN-",
             details=_journal_details),
        Step(NS_FINANCIALS, "close_books", "update", "accounting_period", "NSPERIOD-"),
        hour=18, probability=0.7,
    ),
    # A people manager approves the absence, then completes the talent check-in.
    CrossAppLink(
        "absence_to_talent", PEOPLE_MANAGER,
        Step(HCM_ABSENCE, "close_absence_case", "update", "absence", "ABS-"),
        Step(HCM_TALENT, "log_talent_check_in", "create", "check_in", "CHK-"),
        hour=19, probability=0.75,
    ),
    # A sales rep wins the CX opportunity, then books the fulfillment order in SCM.
    CrossAppLink(
        "opportunity_to_order", SALES_REP,
        Step(CX_SALES, "win_opportunity", "update", "opportunity", "CXOPP-"),
        Step(SCM_ORDER_MGMT, "create_sales_order", "create", "sales_order", "SO-",
             details=_order_details),
        hour=19, probability=0.65,
    ),
)

SHOP = Shop(
    key="oracle",
    tenant_id="umbrella-holdings",
    display_name="Umbrella Holdings (Oracle shop)",
    routines=_ROUTINES,
    cross_app=_CROSS_APP,
    country="US",
    region="TX",
)
