# Arena design: `structured_output`

## Goal

The agent must return data conforming to a fixed JSON schema, after using `search`
to fill the fields. Tests each framework's structured/typed-output support and how
gracefully it recovers from a schema violation.

## Schema

```json
{
  "type": "object",
  "required": ["name", "year", "height_m", "sources"],
  "properties": {
    "name":     {"type": "string"},
    "year":     {"type": "integer"},
    "height_m": {"type": "number"},
    "sources":  {"type": "array", "items": {"type": "string"}, "minItems": 1}
  },
  "additionalProperties": false
}
```

## Task

~15 items: "Return the record for <landmark>." Gold values come from the corpus.

## Scoring (mechanical)

- output parses as JSON and validates against the schema (add a `json_schema`
  check type using a vendored tiny validator or `jsonschema` as a dev dep of the
  scorer only)
- `year` and `height_m` match gold within tolerance
- `sources` non-empty

## Notes

- Adapters may use native structured output (Pydantic AI, response_format,
  tool-as-schema) — which mechanism they use is a finding for the feature matrix.
- One retry on invalid JSON is allowed and counted (report `mean_llm_calls`).
- Mock script returns a valid JSON object per item; include one scenario that
  returns bad JSON first to exercise the retry path.
