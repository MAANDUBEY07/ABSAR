"""Optional telemetry. No exporter is installed or configured implicitly."""


def strip_sensitive(event, hint):
    for key in ("request", "user", "breadcrumbs", "extra", "contexts"):
        event.pop(key, None)
    # Avoid exception text, local variables, SQL values and provider payloads.
    event.pop("exception", None)
    event.pop("message", None)
    event.pop("logentry", None)
    return event


def configure(app, settings):
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            send_default_pii=False,
            include_local_variables=False,
            before_send=strip_sensitive,
            before_breadcrumb=lambda breadcrumb, hint: None,
        )
    if settings.otel_enabled:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,ready")
