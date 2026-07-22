from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..core.contracts import QueryOutcome, QuestionSpec
from ..governance.sql_guard import SQLGuard, UnsafeSQL
from ..knowledge_graph.base import SemanticGraphRepository
from ..llm_control.base import LLMAdapter, LLMError
from ..semantic_query import (
    OPERATOR_REGISTRY_VERSION,
    SemanticQueryCompiler,
    SemanticResultVerifier,
)
from ..storage.database import Database


class GovernedQueryPipeline:
    def __init__(
        self,
        database: Database,
        llm: LLMAdapter,
        graph: SemanticGraphRepository,
        *,
        row_limit: int = 100,
    ):
        if row_limit < 1:
            raise ValueError("row_limit must be at least 1.")
        self.database = database
        self.llm = llm
        self.row_limit = row_limit
        self.graph = graph
        self.compiler = SemanticQueryCompiler()
        self.verifier = SemanticResultVerifier()

    def run(self, question: str) -> QueryOutcome:
        if not question.strip():
            raise ValueError("Question must not be empty.")
        spec = self.llm.interpret(question.strip())

        stop = self._preflight(spec)
        if stop:
            outcome = QueryOutcome(
                status="STOP",
                assurance="EXPLORATORY_NOT_CERTIFIED",
                question_spec=spec,
                stop_reason=stop,
                findings=stop,
            )
            self._audit(outcome)
            return outcome

        context = self.graph.retrieve(spec)
        plan = None
        try:
            plan = self.llm.plan_query(spec, context)
            if plan.operation == "graph":
                rows = self.graph.execute_graph_plan(
                    plan, context, row_limit=self.row_limit
                )
                verification = self.verifier.verify_graph(
                    plan, rows, row_limit=self.row_limit
                )
                sql = None
                parameters: tuple[Any, ...] = ()
                compiler_version = None
                execution_mode = "KGRAPH_PLAN_EXECUTED"
            else:
                if not context.datasets:
                    raise ValueError(
                        "MISSING_SEMANTIC_CONTEXT: no approved dataset matched the question."
                    )
                compiled = self.compiler.compile(plan, context, spec)
                proposal = compiled.proposal
                guard = SQLGuard(self.graph.allowed_datasets())
                with self.database.read_connection() as connection:
                    sql = guard.validate(proposal.sql, proposal.parameters, connection)
                rows = self.database.execute_read(
                    sql,
                    proposal.parameters,
                    allowed_read_objects=guard.runtime_read_sources(sql),
                    row_limit=self.row_limit,
                )
                verification = self.verifier.verify(
                    compiled, rows, row_limit=self.row_limit
                )
                parameters = proposal.parameters
                compiler_version = compiled.compiler_version
                execution_mode = "SEMANTIC_PLAN_COMPILED"
            findings = verification.findings
        except (LLMError, UnsafeSQL, sqlite3.Error, ValueError) as exc:
            rejected_provenance = (
                {
                    "execution_mode": "SEMANTIC_PLAN_REJECTED",
                    "semantic_plan": plan.to_dict(),
                    "operator_registry_version": OPERATOR_REGISTRY_VERSION,
                }
                if plan is not None
                else {}
            )
            outcome = QueryOutcome(
                status="STOP",
                assurance="EXPLORATORY_NOT_CERTIFIED",
                question_spec=spec,
                graph_context=context,
                stop_reason=f"QUERY_REJECTED: {exc}",
                findings="The proposed query did not pass the governed execution gate.",
                provenance=rejected_provenance,
            )
            self._audit(outcome)
            return outcome

        outcome = QueryOutcome(
            status="PASS_WITH_LIMITATIONS",
            assurance="EXPLORATORY_NOT_CERTIFIED",
            question_spec=spec,
            graph_context=context,
            sql=sql,
            parameters=parameters,
            rows=rows,
            findings=findings,
            provenance={
                "registry_version": context.registry_version,
                "datasets": [dataset.name for dataset in context.datasets],
                "row_limit": self.row_limit,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "llm_provider": self.llm.name,
                "execution_mode": execution_mode,
                "semantic_plan": plan.to_dict(),
                "compiler_version": compiler_version,
                "operator_registry_version": OPERATOR_REGISTRY_VERSION,
                "verification_status": verification.diagnostics["verification_status"],
                "total_result_rows": verification.total_rows,
                "returned_rows": len(rows),
                "result_truncated": verification.truncated,
                "verification_diagnostics": verification.diagnostics,
                "defaults_applied": list(spec.defaulted_fields),
                "database": self.database.path.name,
            },
        )
        self._audit(outcome)
        return outcome

    @staticmethod
    def _preflight(spec: QuestionSpec) -> str | None:
        if spec.consequence_class == "high":
            return "HUMAN_APPROVAL_REQUIRED: high-consequence questions cannot auto-execute."
        if spec.ambiguity_flags:
            return "METHOD_BINDING_AMBIGUOUS: " + "; ".join(spec.ambiguity_flags)
        if not spec.entity_type:
            return "MISSING_METHOD: the question could not be bound to a supported entity."
        return None

    def _audit(self, outcome: QueryOutcome) -> None:
        self.database.record_audit(
            question=outcome.question_spec.original_question,
            question_spec=outcome.question_spec.to_dict(),
            sql=outcome.sql,
            status=outcome.status,
            row_count=len(outcome.rows),
            provider=self.llm.name,
            provenance=outcome.provenance,
        )
