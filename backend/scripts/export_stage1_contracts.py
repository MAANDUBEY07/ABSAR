"""Export actual routes and input/response DTOs; --check detects documentation drift."""

import argparse

import ast

import importlib

import inspect

import json

import sys

from pathlib import Path

from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

app = importlib.import_module("main").app


def artifacts():

    spec = app.openapi()

    schemas = dict(spec.get("components", {}).get("schemas", {}))

    for folder in ("schemas", "models"):
        for path in (ROOT / "app" / folder).glob("*.py"):
            module = importlib.import_module(f"app.{folder}.{path.stem}")

            for name, cls in vars(module).items():
                if inspect.isclass(cls) and issubclass(cls, BaseModel) and cls is not BaseModel:
                    schema = cls.model_json_schema(ref_template="#/definitions/{model}")

                    schemas.update(schema.pop("$defs", {}))

                    schemas[name] = schema

    rows = []

    for path in (ROOT / "app/routes").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))

        for function in tree.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for deco in function.decorator_list:
                if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute):
                    continue

                if deco.func.attr not in {"get", "post", "put", "patch", "delete"}:
                    continue

                if not deco.args or not isinstance(deco.args[0], ast.Constant):
                    continue

                for prefix in ["/api"] if path.stem == "legacy" else ["/api/v1", "/api"]:
                    route = prefix + deco.args[0].value

                    operation = (
                        spec.get("paths", {})
                        .get(route if path.stem == "legacy" else "/api/v1" + deco.args[0].value, {})
                        .get(deco.func.attr, {})
                    )

                    args = [arg.arg for arg in function.args.args]

                    rows.append(
                        dict(
                            method=deco.func.attr.upper(),
                            route=route,
                            authentication="Bearer; owner-scoped private resources"
                            if "owner" in args
                            else "Public; legacy auth still provider/environment gated",
                            request_body=operation.get("requestBody"),
                            parameters=operation.get("parameters", []),
                            handler=f"app/routes/{path.name}:{function.lineno} ({function.name})",
                            storage=STORAGE.get(path.stem, "See handler"),
                            status=STATUS.get(
                                path.stem, "Implemented; covered by local regression suite"
                            ),
                            success=SUCCESS.get(
                                path.stem, "Envelope data from handler; inspect source reference"
                            ),
                            errors="401 authentication; 404 owned resource; 409 state/conflict; 422 validation; 503 dependency (as applicable)",
                            frontend_consumer="Not verified against Member 3 completed branch; API client base /api/v1 exists locally",
                            scope="Development-only compatibility; unavailable in hosted mode"
                            if prefix == "/api"
                            else "Canonical",
                            coverage="Local API/adapter suite; see test_persistent.py, test_member2_journey.py, test_stage1.py; per-operation live coverage not claimed",
                        )
                    )

    for route in ("/", "/health", "/api/health", "/ready"):
        rows.append(
            dict(
                method="GET",
                route=route,
                authentication="Public",
                request_body=None,
                parameters=[],
                handler="main.py:health/ready",
                storage="None for health; schema/store/broker for ready",
                status="Migrated local startup smoke passed",
                success="Direct status JSON",
                errors="503 when not ready",
                frontend_consumer="Health monitoring",
                scope="Operational",
                coverage="Phase 2 isolated migrated startup smoke",
            )
        )
    rows.sort(key=lambda row: (row["route"], row["method"]))

    contract = dict(
        title="AVSAR Phase 2 observed backend contracts",
        version="phase2",
        definitions=schemas,
        openapi_reference="openapi.json",
        endpoints=rows,
        success_envelope={
            "data": "endpoint-specific payload",
            "meta": "pagination or empty object",
        },
        error_envelope={
            "detail": "message or validation field locations",
            "error": {"code": "string", "message": "string", "request_id": "string"},
        },
        response_validation_note="Most handlers have no response_model; schemas describe DTOs and observed payloads, not universal runtime response validation.",
    )

    # Contract references use definitions; OpenAPI keeps its own components references.
    contract = json.loads(json.dumps(contract).replace("#/components/schemas/", "#/definitions/"))
    lines = [
        "# Backend endpoint inventory - Phase 2",
        "",
        "Generated from route decorators and current OpenAPI; no duplicate prefix is added. Includes hidden development aliases. Full request schemas/parameters are in API_CONTRACTS.json and openapi.json. Every route has handler, storage, status and coverage information below. Registration does not establish live provider readiness.",
        "",
        "Health: GET /, /health, /api/health and /ready are public direct status JSON; /ready checks schema version, configured document store and broker when required. Local migrated startup smoke verified all relevant baseline statuses.",
        "",
        "| Method | Route | Auth | Request | Success payload | Storage | Status / scope | Coverage |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for row in rows:
        body = row["request_body"] or {}

        request = (
            json.dumps(body.get("content", {}), separators=(",", ":"))
            if body
            else "No body; parameters in OpenAPI"
        )

        lines.append(
            "| "
            + " | ".join(
                [
                    row["method"],
                    "`" + row["route"] + "`",
                    row["authentication"],
                    request.replace("|", "/"),
                    row["success"],
                    row["storage"],
                    row["status"] + "; " + row["scope"],
                    row["coverage"],
                ]
            )
            + " |"
        )

    lines += [
        "",
        "Shared errors: " + rows[0]["errors"],
        "",
        "Frontend consumers: completed Member 3 code not verified here. The local client uses /api/v1; see INTEGRATION_CONTRACTS.md for exact workflow requirements.",
    ]

    return {
        "API_CONTRACTS.json": json.dumps(contract, indent=2) + "\n",
        "openapi.json": json.dumps(spec, indent=2) + "\n",
        "ENDPOINT_INVENTORY.md": "\n".join(lines) + "\n",
    }


STORAGE = {
    "auth": "SQL profiles; signed JWT",
    "profile": "SQL profiles/skills/education/preferences",
    "opportunities": "Mongo opportunities or SQL LocalDocument",
    "discovery": "SQL Job/Outbox; raw_listings/opportunities",
    "eligibility": "SQL profile; document opportunities/feedback",
    "resume": "SQL documents/Job; skill_analysis",
    "trust": "verification_results/source snapshots",
    "applications": "SQL applications/versions/approvals/audit/outbox",
    "calendar": "SQL applications + opportunities",
    "operations": "SQL jobs/notifications/preferences",
    "notices": "SQL documents/jobs + extracted_notices/opportunities",
    "career": "SQL goals/milestones; checkpoints/agent_runs",
    "readiness": "SQL assessments/attempts/jobs",
    "documents": "SQL user_documents",
    "legacy": "SQL/local compatibility; see handler",
}

STATUS = {
    "notices": "Conditional: deterministic text draft or configured AI PDF adapter; human confirmation required",
    "resume": "Member 1 deterministic analyzer integrated through owned result adapter",
    "trust": "Member 1 source assessment and independent backend risk evidence integrated",
    "discovery": "Configured RSS and operator-enabled source adapters; duplicate reviews never auto-merge",
    "legacy": "Compatibility; recovery/MFA and prepare/answer may return 503",
}

SUCCESS = {
    "auth": "Envelope identity/config/logout; legacy signup/login return direct access_token/token_type",
    "profile": "Envelope ProfileResponse",
    "opportunities": "Envelope OpportunityDocument or list + pagination meta",
    "eligibility": "Envelope match/list/feedback or EligibilityEvaluationResponse (route-dependent)",
    "resume": "Envelope upload acknowledgement or skill comparison/roadmap/progress",
    "trust": "Envelope TrustReport + snapshot fields; history list or allegation",
    "applications": "Envelope versioned application/list, status-count map, or submission receipt",
    "calendar": "Envelope list of application deadline events",
    "operations": "Envelope job/result/cancel or notifications/preferences",
    "notices": "Envelope upload/job acknowledgement, notice state/draft or confirmed opportunity",
    "career": "Envelope goal/plan/control/milestone",
    "readiness": "Envelope assessment/questions/answer/code-job/result/progress",
    "documents": "Envelope private document summaries",
    "legacy": "Legacy direct payload or explicit 503; not canonical frontend contracts",
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--check", action="store_true")

    args = parser.parse_args()

    for name, value in artifacts().items():
        target = ROOT.parent / "docs" / name

        if args.check:
            assert target.read_text(encoding="utf-8") == value, f"Contract drift: {name}"

        else:
            target.write_text(value, encoding="utf-8")

    print("Contract export verified" if args.check else "Contracts and inventory exported")
