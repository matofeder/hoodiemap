-- Property presentations and buyer leads.
CREATE TABLE presentations (
  id          text PRIMARY KEY,                    -- public, unguessable (12 url-safe chars)
  edit_token  text NOT NULL,                       -- secret; every write needs it
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz,                         -- demos: after it buyers get 410
  demo_for    text,                                -- "Ukážka pre …"
  source_url  text,                                -- the portal listing a demo was imported from
  data        jsonb NOT NULL,                      -- the editable listing (presentations.PresentationData)
  scene       jsonb NOT NULL                       -- /api/scene snapshot for the location
);

CREATE TABLE leads (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  presentation_id  text NOT NULL REFERENCES presentations(id) ON DELETE CASCADE,
  created_at       timestamptz NOT NULL DEFAULT now(),
  name             text NOT NULL,
  email            text,
  phone            text,
  message          text
);
CREATE INDEX leads_by_presentation ON leads (presentation_id, id DESC);
