# Arena design: `structured_output`

> **Implemented** in `arenas/structured_output/` (15 items). This section is now
> reference notes; where the build diverged from the original design it is called
> out inline.

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

15 items: "Return the record for &lt;landmark&gt;." (Eiffel Tower, Golden Gate
Bridge, Statue of Liberty, Empire State Building, Burj Khalifa, CN Tower, Space
Needle, Willis Tower, Gateway Arch, Washington Monument, Elizabeth Tower, Leaning
Tower of Pisa, Christ the Redeemer, Tokyo Tower, Petronas Towers). Gold values come
from `arena/tools/corpus.json`, which was grown to 27 passages for this arena.

## Scoring (mechanical)

Per item, all must pass:

- `json_schema` — output parses (whole string / ```json fence / first balanced
  span) and validates against the schema. The validator is a ~40-line inline
  function in `arena/scorer.py` (`validate_schema`) — no `jsonschema` dependency;
  the harness core stays stdlib-only.
- `json_path_equals` on `name` (case-insensitive string match)
- `json_path_equals` on `year` (exact)
- `json_path_equals` on `height_m` (numeric, `tol: 1`)
- `tool_used` `search`

## Notes

- Adapters may use native structured output (Pydantic AI result types,
  `response_format`, tool-as-schema) — which mechanism they use is a finding for
  the feature matrix. The shipped adapters currently satisfy the schema by
  prompt instruction alone.
- **Diverges from the design:** the mock script returns a valid JSON object for
  every item (one `search` turn, then the record). The "bad JSON first, then
  retry" scenario was dropped so the arena stays 100% green in mock mode for
  adapters that don't implement a JSON-repair retry (per methodology §5). Invalid
  JSON recovery is a live-mode concern; revisit with a dedicated retry-path item
  once an adapter opts in.
- `not_contains` and `json_valid` check types were added alongside `json_schema`
  and are available for future items.
