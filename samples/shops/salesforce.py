"""Salesforce shop — an Initech Global tenant running the Salesforce clouds.

Products: Sales Cloud, Service Cloud, Marketing Cloud, CPQ, and Experience
Cloud. Each cloud is broken into the modules a real org would configure, driven
by role-appropriate personas. Salesforce orgs almost always federate identity,
so every persona authenticates by ``sso_subject``.
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

_SALES_CONN = "salesforce-platform-events"
_VERSION = "4.2.0"

SALES_LEADS = Module(
    "sfdc_sales_leads", "sfdc-sales-prod", _SALES_CONN, _VERSION,
    "Salesforce Sales Cloud", "Leads",
)
SALES_OPPORTUNITIES = Module(
    "sfdc_sales_opportunities", "sfdc-sales-prod", _SALES_CONN, _VERSION,
    "Salesforce Sales Cloud", "Opportunities",
)
SALES_FORECASTING = Module(
    "sfdc_sales_forecasting", "sfdc-sales-prod", _SALES_CONN, _VERSION,
    "Salesforce Sales Cloud", "Forecasting",
)
SALES_ACCOUNTS = Module(
    "sfdc_sales_accounts", "sfdc-sales-prod", _SALES_CONN, _VERSION,
    "Salesforce Sales Cloud", "Accounts & Contacts",
)

SERVICE_CASES = Module(
    "sfdc_service_cases", "sfdc-service-prod", _SALES_CONN, _VERSION,
    "Salesforce Service Cloud", "Cases",
)
SERVICE_KNOWLEDGE = Module(
    "sfdc_service_knowledge", "sfdc-service-prod", _SALES_CONN, _VERSION,
    "Salesforce Service Cloud", "Knowledge",
)
SERVICE_OMNI = Module(
    "sfdc_service_omni", "sfdc-service-prod", _SALES_CONN, _VERSION,
    "Salesforce Service Cloud", "Omni-Channel",
)

MKT_JOURNEYS = Module(
    "sfdc_marketing_journeys", "sfmc-prod", "marketing-cloud-connector", "2.9.1",
    "Salesforce Marketing Cloud", "Journeys",
)
MKT_CAMPAIGNS = Module(
    "sfdc_marketing_campaigns", "sfmc-prod", "marketing-cloud-connector", "2.9.1",
    "Salesforce Marketing Cloud", "Campaigns",
)

CPQ_QUOTES = Module(
    "sfdc_cpq_quotes", "sfdc-cpq-prod", _SALES_CONN, _VERSION,
    "Salesforce CPQ", "Quotes",
)
CPQ_APPROVALS = Module(
    "sfdc_cpq_approvals", "sfdc-cpq-prod", _SALES_CONN, _VERSION,
    "Salesforce CPQ", "Approvals",
)

EXP_PARTNER = Module(
    "sfdc_experience_partner", "sfdc-exp-prod", _SALES_CONN, _VERSION,
    "Salesforce Experience Cloud", "Partner Portal",
)
EXP_CUSTOMER = Module(
    "sfdc_experience_customer", "sfdc-exp-prod", _SALES_CONN, _VERSION,
    "Salesforce Experience Cloud", "Customer Community",
)

# ---------------------------------------------------------------------------
# Personas — all federated SSO
# ---------------------------------------------------------------------------

_SSO = "sso_subject"

SDR = Persona("sso|initech|a1b2c3", "Priya Kapoor", ("sales_development_rep",), _SSO)
AE_ONE = Persona("sso|initech|d4e5f6", "Jordan Blake", ("account_executive",), _SSO)
AE_TWO = Persona("sso|initech|g7h8i9", "Wei Zhang", ("account_executive",), _SSO)
SALES_MANAGER = Persona("sso|initech|j1k2l3", "Rosa Iglesias", ("sales_manager",), _SSO)
SALES_OPS = Persona("sso|initech|m4n5o6", "Ben Carter", ("sales_ops",), _SSO)

SUPPORT_AGENT_ONE = Persona("sso|initech|p7q8r9", "Amara Diallo", ("support_agent",), _SSO)
SUPPORT_AGENT_TWO = Persona("sso|initech|s1t2u3", "Nikhil Rao", ("support_agent",), _SSO)
SUPPORT_LEAD = Persona("sso|initech|v4w5x6", "Chloe Martin", ("support_team_lead",), _SSO)
KNOWLEDGE_MANAGER = Persona("sso|initech|y7z8a9", "Dmitri Sokolov", ("knowledge_manager",), _SSO)

MKT_SPECIALIST = Persona("sso|initech|b1c2d3", "Yara Haddad", ("marketing_specialist",), _SSO)
CAMPAIGN_MANAGER = Persona("sso|initech|e4f5g6", "Liam O'Brien", ("campaign_manager",), _SSO)

DEAL_DESK_ANALYST = Persona("sso|initech|h7i8j9", "Sana Qureshi", ("deal_desk_analyst",), _SSO)
SALES_ENGINEER = Persona("sso|initech|k1l2m3", "Erik Larsson", ("sales_engineer",), _SSO)
DEAL_DESK_MANAGER = Persona("sso|initech|n4o5p6", "Grace Kim", ("deal_desk_manager",), _SSO)

PARTNER_USER = Persona("sso|partner|q7r8s9", "Marco Rossi", ("partner_user",), _SSO)
COMMUNITY_CUSTOMER = Persona("sso|community|t1u2v3", "Aisha Bello", ("customer",), _SSO)

# Stable object pools for active-object density.
_KEY_ACCOUNTS = ("ACC-004821", "ACC-004833", "ACC-004850", "ACC-004867")
_OPEN_OPPS = ("OPP-018204", "OPP-018231", "OPP-018255", "OPP-018290", "OPP-018312")
_HOT_CASES = ("CASE-00204811", "CASE-00204833", "CASE-00204850")


# ---------------------------------------------------------------------------
# Detail generators
# ---------------------------------------------------------------------------

_STAGES = ("Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost")
_PRIORITIES = ("Low", "Medium", "High", "Critical")


def _opp_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 8000, 750000),
            "stage": pick(rng, *_STAGES),
            "forecast_category": pick(rng, "Pipeline", "Best Case", "Commit"),
            "close_quarter": pick(rng, "Q1-FY27", "Q2-FY27", "Q3-FY27")}


def _lead_details(rng: random.Random) -> dict[str, Any]:
    return {"source": pick(rng, "webinar", "inbound", "event", "partner", "cold_outreach"),
            "rating": pick(rng, "Cold", "Warm", "Hot"),
            "industry": pick(rng, "SaaS", "Manufacturing", "Healthcare", "Finance")}


def _case_details(rng: random.Random) -> dict[str, Any]:
    return {"priority": pick(rng, *_PRIORITIES),
            "origin": pick(rng, "Email", "Phone", "Web", "Chat"),
            "product": pick(rng, "Platform", "Analytics", "Mobile SDK", "Billing"),
            "sla_minutes": pick(rng, "60", "240", "480")}


def _quote_details(rng: random.Random) -> dict[str, Any]:
    return {**money(rng, 12000, 900000),
            "term_months": pick(rng, "12", "24", "36"),
            "discount_pct": round(rng.uniform(0, 35), 1),
            "line_count": rng.randint(2, 14)}


def _campaign_details(rng: random.Random) -> dict[str, Any]:
    return {"channel": pick(rng, "email", "webinar", "paid_social", "field_event"),
            "audience_size": rng.randint(500, 45000),
            "budget_usd": round(rng.uniform(2000, 120000), 2)}


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

_ROUTINES: tuple[Routine, ...] = (
    # Sales Cloud — Leads
    Routine(
        SALES_LEADS, (SDR,), "weekday", 8,
        (
            Activity("create_lead", "create", "lead", "LEAD-", details=_lead_details),
            Activity("qualify_lead", "update", "lead", "LEAD-",
                     metadata=lambda r: {"outcome": pick(r, "MQL", "SQL", "disqualified")}),
        ),
        occurrences=(4, 10),
    ),
    # Sales Cloud — Opportunities
    Routine(
        SALES_OPPORTUNITIES, (AE_ONE, AE_TWO), "weekday", 9,
        (
            Activity("view_opportunity", "read", "opportunity", "OPP-", id_pool=_OPEN_OPPS),
            Activity("update_stage", "update", "opportunity", "OPP-", id_pool=_OPEN_OPPS,
                     details=_opp_details),
            Activity("log_activity", "create", "task", "TASK-",
                     metadata=lambda r: {"type": pick(r, "call", "email", "meeting")}),
        ),
        occurrences=(2, 5), device_mix=("desktop", "desktop", "mobile"),
    ),
    # Sales Cloud — Forecasting
    Routine(
        SALES_FORECASTING, (SALES_MANAGER,), "weekly", 16,
        (Activity("submit_forecast", "update", "forecast", "FCT-",
                  details=lambda r: {**money(r, 250000, 4000000),
                                     "category": pick(r, "Commit", "Best Case")}),),
    ),
    # Sales Cloud — Accounts
    Routine(
        SALES_ACCOUNTS, (SALES_OPS,), "weekday", 11,
        (
            Activity("update_account", "update", "account", "ACC-", id_pool=_KEY_ACCOUNTS),
            Activity("create_contact", "create", "contact", "CON-"),
        ),
        occurrences=(1, 4),
    ),
    # Service Cloud — Cases
    Routine(
        SERVICE_CASES, (SUPPORT_AGENT_ONE, SUPPORT_AGENT_TWO), "weekday", 10,
        (
            Activity("create_case", "create", "case", "CASE-", details=_case_details),
            Activity("add_case_comment", "update", "case", "CASE-", id_pool=_HOT_CASES),
            Activity("resolve_case", "update", "case", "CASE-", id_pool=_HOT_CASES,
                     metadata=lambda r: {"resolution": pick(r, "fixed", "workaround",
                                                            "no_repro")}),
        ),
        occurrences=(5, 12), device_mix=("desktop",),
    ),
    # Service Cloud — Knowledge
    Routine(
        SERVICE_KNOWLEDGE, (KNOWLEDGE_MANAGER,), "weekly", 13,
        (Activity("publish_article", "create", "knowledge_article", "KA-",
                  metadata=lambda r: {"category": pick(r, "how-to", "troubleshooting",
                                                       "release-note")}),),
        occurrences=(1, 3),
    ),
    # Service Cloud — Omni-Channel
    Routine(
        SERVICE_OMNI, (SUPPORT_LEAD,), "weekday", 9,
        (Activity("route_work_item", "update", "work_item", "WI-",
                  metadata=lambda r: {"queue": pick(r, "tier1", "tier2", "billing"),
                                      "wait_seconds": r.randint(5, 900)}),),
        occurrences=(3, 8),
    ),
    # Marketing Cloud — Journeys
    Routine(
        MKT_JOURNEYS, (MKT_SPECIALIST,), "weekday", 10,
        (
            Activity("build_journey", "create", "journey", "JNY-",
                     metadata=lambda r: {"steps": r.randint(3, 12)}),
            Activity("send_journey_email", "create", "email_send", "SEND-",
                     details=lambda r: {"recipients": r.randint(1000, 80000),
                                        "template": pick(r, "nurture-a", "nurture-b",
                                                         "reengage")}),
        ),
        occurrences=(1, 3),
    ),
    # Marketing Cloud — Campaigns
    Routine(
        MKT_CAMPAIGNS, (CAMPAIGN_MANAGER,), "weekly", 11,
        (Activity("create_campaign", "create", "campaign", "CMP-", details=_campaign_details),),
    ),
    # CPQ — Quotes
    Routine(
        CPQ_QUOTES, (DEAL_DESK_ANALYST, SALES_ENGINEER), "weekday", 14,
        (
            Activity("create_quote", "create", "quote", "Q-", details=_quote_details),
            Activity("configure_product", "update", "quote_line", "QL-",
                     metadata=lambda r: {"product": pick(r, "Platform", "Analytics", "Support")}),
            Activity("generate_quote_doc", "create", "quote_document", "QDOC-"),
        ),
        occurrences=(1, 4),
    ),
    # CPQ — Approvals
    Routine(
        CPQ_APPROVALS, (DEAL_DESK_MANAGER,), "weekday", 15,
        (Activity("approve_discount", "approve", "approval", "APR-",
                  metadata=lambda r: {"discount_pct": round(r.uniform(10, 40), 1),
                                      "outcome": pick(r, "approved", "rejected",
                                                      "escalated")}),),
        occurrences=(2, 6), device_mix=("desktop", "mobile"),
    ),
    # Experience Cloud — Partner Portal
    Routine(
        EXP_PARTNER, (PARTNER_USER,), "weekly", 12,
        (Activity("register_deal", "create", "deal_registration", "DR-",
                  details=lambda r: money(r, 5000, 300000)),),
        occurrences=(1, 3),
    ),
    # Experience Cloud — Customer Community
    Routine(
        EXP_CUSTOMER, (COMMUNITY_CUSTOMER,), "weekday", 13,
        (Activity("open_community_case", "create", "case", "CCASE-", details=_case_details),),
        occurrences=(1, 2),
    ),
)


# ---------------------------------------------------------------------------
# Cross-cloud workflows
# ---------------------------------------------------------------------------

# Single-persona cross-cloud journeys, isolated in the evening so the profiler
# reads each as one clean cross-cloud sequence.
_CROSS_APP: tuple[CrossAppLink, ...] = (
    # An AE converts the qualified lead, then spins up the opportunity.
    CrossAppLink(
        "lead_to_opportunity", AE_ONE,
        Step(SALES_LEADS, "convert_lead", "update", "lead", "LEAD-"),
        Step(SALES_OPPORTUNITIES, "create_opportunity", "create", "opportunity", "OPP-",
             details=_opp_details),
        hour=18, probability=0.8,
    ),
    # An AE moves the deal to Proposal, then builds the CPQ quote for it.
    CrossAppLink(
        "opportunity_to_quote", AE_TWO,
        Step(SALES_OPPORTUNITIES, "move_to_proposal", "update", "opportunity", "OPP-"),
        Step(CPQ_QUOTES, "create_quote", "create", "quote", "Q-", details=_quote_details),
        hour=18, probability=0.7,
    ),
    # A support lead escalates the case, then links a knowledge article to it.
    CrossAppLink(
        "case_to_knowledge", SUPPORT_LEAD,
        Step(SERVICE_CASES, "escalate_case", "update", "case", "CASE-"),
        Step(SERVICE_KNOWLEDGE, "link_article_to_case", "update", "knowledge_article", "KA-"),
        hour=19, probability=0.65,
    ),
    # A sales manager reviews an opportunity, then submits the updated forecast.
    CrossAppLink(
        "opportunity_to_forecast", SALES_MANAGER,
        Step(SALES_OPPORTUNITIES, "review_opportunity", "read", "opportunity", "OPP-"),
        Step(SALES_FORECASTING, "submit_forecast", "update", "forecast", "FCT-",
             details=lambda r: money(r, 250000, 4000000)),
        hour=19, probability=0.8,
    ),
)

SHOP = Shop(
    key="salesforce",
    tenant_id="initech-global",
    display_name="Initech Global (Salesforce shop)",
    routines=_ROUTINES,
    cross_app=_CROSS_APP,
    country="US",
    region="NY",
)
