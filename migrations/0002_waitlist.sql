-- "Prever si byt pred kúpou" demand test: page events (no cookies, no personal data) and sign-ups.
CREATE TABLE landing_events (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at  timestamptz NOT NULL DEFAULT now(),
  kind        text NOT NULL CHECK (kind IN ('view', 'cta')),
  variant     text NOT NULL,      -- the price shown, e.g. "9" or "19"
  source      text,               -- utm_source (fb, google, …)
  campaign    text                -- utm_campaign
);
CREATE INDEX landing_events_by_time ON landing_events (created_at);

CREATE TABLE waitlist (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  created_at   timestamptz NOT NULL DEFAULT now(),
  email        text NOT NULL UNIQUE,
  timeframe    text CHECK (timeframe IN ('3m', '12m', 'browsing')),
  listing_url  text,               -- the flat they are looking at, if they shared it
  variant      text NOT NULL,
  source       text,
  campaign     text
);
