"""Realistic multi-application seed data for archetypal enterprise "shops".

Each shop (SAP, Salesforce, Oracle) is a single tenant running a stack of
products, each product broken into modules, each module driven by distinct
personas. The generators here expand compact declarative definitions into
universal-schema events that flow through the real ingestion, graph, and
profiler paths.
"""
