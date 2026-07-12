"""Static catalog of users and applications used to synthesize seed events.

These definitions describe a small fictional company ("acme-corp") so that the
seed generator can produce recognizable, thick behavioral patterns for demos.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """A person who performs actions across the sample applications."""

    native_user_id: str
    display_name: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class Application:
    """A source application that emits events through a connector."""

    application_id: str
    instance_id: str
    connector: str
    connector_version: str


# Five users with distinct behavioral profiles.
ALICE = User("alice.chen@acme-corp.example", "Alice Chen", ("hr_manager",))
BOB = User("bob.martinez@acme-corp.example", "Bob Martinez", ("engineering_lead",))
CAROL = User("carol.singh@acme-corp.example", "Carol Singh", ("software_engineer",))
DAVE = User("dave.kim@acme-corp.example", "Dave Kim", ("finance_analyst",))
ERIN = User("erin.wong@acme-corp.example", "Erin Wong", ("project_manager",))

USERS: tuple[User, ...] = (ALICE, BOB, CAROL, DAVE, ERIN)

# Developers who perform daily sprint checks in the Jira-like application.
DEVELOPERS: tuple[User, ...] = (BOB, CAROL, ERIN)

# Employees who submit monthly expense reports in the Concur-like application.
EXPENSE_SUBMITTERS: tuple[User, ...] = (BOB, CAROL, DAVE, ERIN)

# Three applications, each with its own connector identity.
JIRA = Application("jira", "jira-prod-01", "jira-connector", "1.4.0")
SUCCESSFACTORS = Application(
    "successfactors", "sf-prod-01", "successfactors-connector", "2.1.0"
)
CONCUR = Application("concur", "concur-prod-01", "concur-connector", "1.0.3")

APPLICATIONS: tuple[Application, ...] = (JIRA, SUCCESSFACTORS, CONCUR)
