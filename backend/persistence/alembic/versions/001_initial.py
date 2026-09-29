"""Initial schema for NerveCenter.

This migration creates all core tables with their columns, indexes, and
pgvector extension support. It follows the v0 schema contracts defined in
the ``schemas/`` package.

Migration order
---------------
1. Create pgvector extension (idempotent).
2. Create tables in dependency order:
   - events (no dependencies)
   - evidence (no dependencies)
   - entities (no dependencies)
   - relationships (depends on entities)
   - claims (no dependencies)
   - decisions (depends on claims)
   - tasks (no dependencies)
   - task_runs (depends on tasks)
   - goals (no dependencies)
   - agent_results (depends on tasks)

Vector columns
--------------
- ``events.embedding`` — for semantic search over event payloads.
- ``entities.embedding`` — optional entity embedding storage.

Run
---

    alembic upgrade head

Rollback
--------

    alembic downgrade -1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # events
    op.create_table(
        "events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("parent_event_id", sa.String(), nullable=True),
        sa.Column("stream", sa.String(length=255), nullable=True),
        sa.Column("sequence", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("embedding", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"], unique=False)
    op.create_index("ix_events_category", "events", ["category"], unique=False)
    op.create_index("ix_events_source", "events", ["source"], unique=False)
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"], unique=False, postgresql_using="btree", postgresql_ops={"occurred_at": "DESC"})
    op.create_index("ix_events_subject", "events", ["subject"], unique=False)
    op.create_index("ix_events_trace_id", "events", ["trace_id"], unique=False)
    op.create_index("ix_events_correlation_id", "events", ["correlation_id"], unique=False)
    op.create_index("ix_events_parent_event_id", "events", ["parent_event_id"], unique=False)
    op.create_index("ix_events_stream_sequence", "events", ["stream", "sequence", "occurred_at"], unique=False)

    # evidence
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trust", sa.Float(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("redacted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_source_type", "evidence", ["source_type"], unique=False)
    op.create_index("ix_evidence_source_ref", "evidence", ["source_ref"], unique=False)
    op.create_index("ix_evidence_content_hash", "evidence", ["content_hash"], unique=False)
    op.create_index("ix_evidence_captured_at", "evidence", ["captured_at"], unique=False)
    op.create_index("ix_evidence_source_type_captured_at", "evidence", ["source_type", "captured_at"], unique=False)
    op.create_index("ix_evidence_source_ref_hash", "evidence", ["source_ref", "content_hash"], unique=False)

    # entities
    op.create_table(
        "entities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"], unique=False)
    op.create_index("ix_entities_name", "entities", ["name"], unique=False)
    op.create_index("ix_entities_entity_type_name", "entities", ["entity_type", "name"], unique=False)
    op.create_index("ix_entities_valid_window", "entities", ["valid_from", "valid_to"], unique=False)
    op.create_index("ix_entities_source_evidence_gin", "entities", ["source_evidence"], unique=False, postgresql_using="gin")

    # relationships
    op.create_table(
        "relationships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("source_entity_id", sa.String(), nullable=False),
        sa.Column("target_entity_id", sa.String(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("asserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_entity_id"], ["entities.id"], ),
        sa.ForeignKeyConstraint(["target_entity_id"], ["entities.id"], ),
    )
    op.create_index("ix_relationships_source_target", "relationships", ["source_entity_id", "target_entity_id", "relation_type"], unique=False)
    op.create_index("ix_relationships_source_entity_id", "relationships", ["source_entity_id"], unique=False)
    op.create_index("ix_relationships_target_entity_id", "relationships", ["target_entity_id"], unique=False)
    op.create_index("ix_relationships_relation_type", "relationships", ["relation_type"], unique=False)
    op.create_index("ix_relationships_evidence_gin", "relationships", ["evidence"], unique=False, postgresql_using="gin")

    # claims
    op.create_table(
        "claims",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("statement", sa.String(), nullable=False),
        sa.Column("subject_entity_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contradicting_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("derived_from_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supersedes_claim_id", sa.String(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["subject_entity_id"], ["entities.id"], ),
        sa.ForeignKeyConstraint(["supersedes_claim_id"], ["claims.id"], ),
    )
    op.create_index("ix_claims_status", "claims", ["status"], unique=False)
    op.create_index("ix_claims_status_subject", "claims", ["status", "subject_entity_id"], unique=False)
    op.create_index("ix_claims_status_created_at", "claims", ["status", "created_at"], unique=False)

    # decisions
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("statement", sa.String(), nullable=False),
        sa.Column("mechanism", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("supporting_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("planned_change_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ),
        sa.ForeignKeyConstraint(["planned_change_id"], ["planned_changes.id"], ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ),
    )
    op.create_index("ix_decisions_claim_id", "decisions", ["claim_id"], unique=False)
    op.create_index("ix_decisions_claim_id_mechanism", "decisions", ["claim_id", "mechanism"], unique=False)
    op.create_index("ix_decisions_action", "decisions", ["action"], unique=False)
    op.create_index("ix_decisions_action_created_at", "decisions", ["action", "created_at"], unique=False)

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.BigInteger(), nullable=False),
        sa.Column("goal_id", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column("assignee_agent_id", sa.String(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parent_task_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], ),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"], unique=False)
    op.create_index("ix_tasks_status_priority", "tasks", ["status", "priority", "created_at"], unique=False)
    op.create_index("ix_tasks_goal_id", "tasks", ["goal_id"], unique=False)
    op.create_index("ix_tasks_decision_id", "tasks", ["decision_id"], unique=False)
    op.create_index("ix_tasks_assignee_agent_id", "tasks", ["assignee_agent_id"], unique=False)
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"], unique=False)
    op.create_index("ix_tasks_scheduled_at_status", "tasks", ["scheduled_at", "status"], unique=False)

    # task_runs
    op.create_table(
        "task_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("result_ref", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("logs_ref", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ),
    )
    op.create_index("ix_task_runs_task_id", "task_runs", ["task_id"], unique=False)
    op.create_index("ix_task_runs_task_id_attempt", "task_runs", ["task_id", "attempt"], unique=False)
    op.create_index("ix_task_runs_task_id_status", "task_runs", ["task_id", "status"], unique=False)
    op.create_index("ix_task_runs_agent_id", "task_runs", ["agent_id"], unique=False)
    op.create_index("ix_task_runs_model_id", "task_runs", ["model_id"], unique=False)

    # goals
    op.create_table(
        "goals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subgoal_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.BigInteger(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_entity_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_goals_status", "goals", ["status"], unique=False)
    op.create_index("ix_goals_status_priority", "goals", ["status", "priority", "created_at"], unique=False)
    op.create_index("ix_goals_status_deadline", "goals", ["status", "deadline"], unique=False)
    op.create_index("ix_goals_subgoal_ids_gin", "goals", ["subgoal_ids"], unique=False, postgresql_using="gin")

    # agent_results
    op.create_table(
        "agent_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("task_run_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("structured_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("produced_entity_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("produced_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("produced_claim_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("tokens_used", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.id"], ),
    )
    op.create_index("ix_agent_results_task_run_id", "agent_results", ["task_run_id"], unique=False)
    op.create_index("ix_agent_results_task_run_id_status", "agent_results", ["task_run_id", "status"], unique=False)
    op.create_index("ix_agent_results_agent_id", "agent_results", ["agent_id"], unique=False)
    op.create_index("ix_agent_results_agent_id_created_at", "agent_results", ["agent_id", "created_at"], unique=False)

    # planned_changes (used by decisions)
    op.create_table(
        "planned_changes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.Integer(), nullable=False),
        sa.Column("subject_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_decision_id", sa.String(), nullable=True),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rollback", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_decision_id"], ["decisions.id"], ),
    )
    op.create_index("ix_planned_changes_change_type", "planned_changes", ["change_type"], unique=False)
    op.create_index("ix_planned_changes_status", "planned_changes", ["status"], unique=False)
    op.create_index("ix_planned_changes_source_decision_id", "planned_changes", ["source_decision_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_planned_changes_source_decision_id", table_name="planned_changes")
    op.drop_index("ix_planned_changes_status", table_name="planned_changes")
    op.drop_index("ix_planned_changes_change_type", table_name="planned_changes")
    op.drop_table("planned_changes")

    op.drop_index("ix_agent_results_agent_id_created_at", table_name="agent_results")
    op.drop_index("ix_agent_results_agent_id", table_name="agent_results")
    op.drop_index("ix_agent_results_task_run_id_status", table_name="agent_results")
    op.drop_index("ix_agent_results_task_run_id", table_name="agent_results")
    op.drop_table("agent_results")

    op.drop_index("ix_goals_subgoal_ids_gin", table_name="goals")
    op.drop_index("ix_goals_status_deadline", table_name="goals")
    op.drop_index("ix_goals_status_priority", table_name="goals")
    op.drop_index("ix_goals_status", table_name="goals")
    op.drop_table("goals")

    op.drop_index("ix_task_runs_model_id", table_name="task_runs")
    op.drop_index("ix_task_runs_agent_id", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id_status", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id_attempt", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id", table_name="task_runs")
    op.drop_table("task_runs")

    op.drop_index("ix_tasks_scheduled_at_status", table_name="tasks")
    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_index("ix_tasks_assignee_agent_id", table_name="tasks")
    op.drop_index("ix_tasks_decision_id", table_name="tasks")
    op.drop_index("ix_tasks_goal_id", table_name="tasks")
    op.drop_index("ix_tasks_status_priority", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_decisions_action_created_at", table_name="decisions")
    op.drop_index("ix_decisions_action", table_name="decisions")
    op.drop_index("ix_decisions_claim_id_mechanism", table_name="decisions")
    op.drop_index("ix_decisions_claim_id", table_name="decisions")
    op.drop_table("decisions")

    op.drop_index("ix_claims_status_created_at", table_name="claims")
    op.drop_index("ix_claims_status_subject", table_name="claims")
    op.drop_index("ix_claims_status", table_name="claims")
    op.drop_table("claims")

    op.drop_index("ix_relationships_evidence_gin", table_name="relationships")
    op.drop_index("ix_relationships_relation_type", table_name="relationships")
    op.drop_index("ix_relationships_target_entity_id", table_name="relationships")
    op.drop_index("ix_relationships_source_entity_id", table_name="relationships")
    op.drop_index("ix_relationships_source_target", table_name="relationships")
    op.drop_table("relationships")

    op.drop_index("ix_entities_source_evidence_gin", table_name="entities")
    op.drop_index("ix_entities_valid_window", table_name="entities")
    op.drop_index("ix_entities_entity_type_name", table_name="entities")
    op.drop_index("ix_entities_name", table_name="entities")
    op.drop_index("ix_entities_entity_type", table_name="entities")
    op.drop_table("entities")

    op.drop_index("ix_evidence_source_ref_hash", table_name="evidence")
    op.drop_index("ix_evidence_captured_at", table_name="evidence")
    op.drop_index("ix_evidence_content_hash", table_name="evidence")
    op.drop_index("ix_evidence_source_ref", table_name="evidence")
    op.drop_index("ix_evidence_source_type_captured_at", table_name="evidence")
    op.drop_index("ix_evidence_source_type", table_name="evidence")
    op.drop_table("evidence")

    op.drop_index("ix_events_stream_sequence", table_name="events")
    op.drop_index("ix_events_parent_event_id", table_name="events")
    op.drop_index("ix_events_correlation_id", table_name="events")
    op.drop_index("ix_events_trace_id", table_name="events")
    op.drop_index("ix_events_subject", table_name="events")
    op.drop_index("ix_events_occurred_at", table_name="events")
    op.drop_index("ix_events_source", table_name="events")
    op.drop_index("ix_events_category", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_table("events")

    op.execute("DROP EXTENSION IF EXISTS vector")
