### Fixed

- Fixed OTLP endpoint resolution defeating the SDK's signal-path handling. `configure_opentelemetry()` read `OTEL_EXPORTER_OTLP_ENDPOINT` itself and passed the value to `OTLPSpanExporter(endpoint=...)`, and an explicitly-passed endpoint is used verbatim — so setting the standard base URL (the spec-correct choice) produced POSTs to the collector root and a 404 per batch, surfaced as nothing louder than a `BatchSpanProcessor` warning. The exporter is now given an endpoint only when it came from the `OPENTELEMETRY_ENDPOINT` Django setting, which is a full signal URL; when the environment configures it, the SDK resolves it and appends `/v1/traces` as intended.
- Fixed `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` being ignored. Setting only the signal-specific variable left `endpoint` unset, so `configure_opentelemetry()` returned early and disabled tracing silently. Both standard variables are now recognised, most-specific first.

### Changed

- Raised the "no endpoint configured, tracing disabled" message from `debug` to `info`, and named the variables that would enable it. A service that silently exports nothing is indistinguishable from a healthy one until somebody goes looking in Tempo.
- The OTLP exporter startup log now names the configuration source (environment vs `OPENTELEMETRY_ENDPOINT`), since the URL finally posted to may differ from the configured value once the SDK appends a signal path.
