-- AHP expert panel: one row per expert and criteria set; weights are computed from these by src/ahp.py.
CREATE TABLE ahp_responses (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at    timestamptz NOT NULL DEFAULT now(),
  set_id        text NOT NULL,          -- score_method.AHP_SETS key, e.g. "rodina"
  expert_name   text NOT NULL,
  expert_role   text NOT NULL,          -- e.g. "urbanista", "realitný znalec"
  judgments     jsonb NOT NULL,         -- {"A|B": 3, "A|C": 0.2, ...} on Saaty's scale
  cr            double precision NOT NULL,
  consistent    boolean NOT NULL
);
CREATE INDEX ahp_responses_by_set ON ahp_responses (set_id, id);
