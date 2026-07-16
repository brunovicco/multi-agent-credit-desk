"""Typed identifiers correlating a credit review workflow across process boundaries.

These mirror the functional identifiers listed alongside the W3C ``traceparent`` in
``docs/architecture-blueprint.md`` section 2.4: ``trace_id`` serves technical observability, while
these identifiers serve functional audit correlation.
"""

from typing import Annotated, NewType

from pydantic import StringConstraints

_NonEmptyId = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

WorkflowId = NewType("WorkflowId", _NonEmptyId)
ContextId = NewType("ContextId", _NonEmptyId)
TaskId = NewType("TaskId", _NonEmptyId)
AgentExecutionId = NewType("AgentExecutionId", _NonEmptyId)
RoutingDecisionId = NewType("RoutingDecisionId", _NonEmptyId)
ArtifactId = NewType("ArtifactId", _NonEmptyId)
