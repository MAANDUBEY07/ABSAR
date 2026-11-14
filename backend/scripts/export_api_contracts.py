"""Export contracts and OpenAPI from the implemented chart modules."""

import json
from pathlib import Path
import sys


def export():
    backend = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend))
    from main import app
    from app.models.opportunity import OpportunityDocument
    from app.schemas.profile import ProfileInput, ProfileResponse
    from app.schemas.opportunity import OpportunityInput
    from app.schemas.eligibility import EligibilityBatch, EligibilityEvaluationResponse
    from app.schemas.resume import ResumeAnalysisResponse, ResumeMatchInput
    from app.schemas.trust import Report, TrustReportResponse
    from app.schemas.application import ApplicationCreate, ApplicationPatch, Revision, Submit
    from app.services.eligibility_engine import APIEligibilityStatus

    definitions = {}
    models = {
        "ProfileInput": ProfileInput,
        "ProfileResponse": ProfileResponse,
        "OpportunityInput": OpportunityInput,
        "OpportunityResponse": OpportunityDocument,
        "EligibilityBatch": EligibilityBatch,
        "EligibilityEvaluationResponse": EligibilityEvaluationResponse,
        "ResumeAnalysisResponse": ResumeAnalysisResponse,
        "ResumeMatchInput": ResumeMatchInput,
        "TrustReportResponse": TrustReportResponse,
        "Report": Report,
        "ApplicationCreate": ApplicationCreate,
        "ApplicationPatch": ApplicationPatch,
        "Revision": Revision,
        "Submit": Submit,
    }
    for name, model in models.items():
        schema = model.model_json_schema(ref_template="#/definitions/{model}")
        definitions.update(schema.pop("$defs", {}))
        definitions[name] = schema
    definitions["EligibilityStatus"] = {
        "type": "string",
        "enum": [status.value for status in APIEligibilityStatus],
    }
    contract = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AVSAR API Contracts",
        "version": "1.1.0",
        "description": "Generated payload schemas. HTTP successes wrap payloads in data/meta; persistent matching has a separate three-status vocabulary.",
        "definitions": definitions,
    }
    docs = backend.parent / "docs"
    (docs / "API_CONTRACTS.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    (docs / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(
        f"Exported {len(definitions)} payload schemas and {len(app.openapi()['paths'])} OpenAPI paths"
    )


if __name__ == "__main__":
    export()
