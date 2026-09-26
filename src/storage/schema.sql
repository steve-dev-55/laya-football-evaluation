-- Schéma SQL minimal du protocole (§4.2) — SQLite.
-- Toute colonne du protocole est présente ; les index servent les requêtes
-- point-in-time (§5.2, §5.3).

CREATE TABLE IF NOT EXISTS matches (
  match_id            TEXT PRIMARY KEY,
  source_match_id     TEXT NOT NULL,
  competition_id      TEXT NOT NULL,
  season              TEXT NOT NULL,
  date_utc            TEXT NOT NULL,
  kickoff_timestamp   TEXT NOT NULL,
  home_team_id        TEXT NOT NULL,
  away_team_id        TEXT NOT NULL,
  home_goals          INTEGER NOT NULL,
  away_goals          INTEGER NOT NULL,
  total_corners       INTEGER,
  total_yellow_cards  INTEGER,
  total_red_cards     INTEGER,
  status              TEXT NOT NULL,
  source_hash         TEXT NOT NULL,
  available_timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_comp_season ON matches(competition_id, season, date_utc);
CREATE INDEX IF NOT EXISTS idx_matches_available ON matches(available_timestamp);

CREATE TABLE IF NOT EXISTS match_events (
  event_id        TEXT PRIMARY KEY,
  match_id        TEXT NOT NULL,
  elapsed_seconds INTEGER NOT NULL,
  period         INTEGER NOT NULL,
  event_type     TEXT NOT NULL,
  team_id        TEXT,
  player_id       TEXT,
  detail         TEXT,
  source_event_id TEXT,
  source_hash    TEXT NOT NULL,
  available_timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_match_time ON match_events(match_id, elapsed_seconds);
CREATE INDEX IF NOT EXISTS idx_events_available ON match_events(available_timestamp);

CREATE TABLE IF NOT EXISTS match_statistics (
  stat_id            TEXT PRIMARY KEY,
  match_id           TEXT NOT NULL,
  available_timestamp TEXT NOT NULL,
  elapsed_seconds    INTEGER NOT NULL,
  team_id            TEXT NOT NULL,
  shots              INTEGER,
  shots_on_target    INTEGER,
  corners            INTEGER,
  yellow_cards       INTEGER,
  red_cards          INTEGER,
  possession         REAL,
  xg                 REAL,
  source_hash        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stats_match_time ON match_statistics(match_id, elapsed_seconds);

CREATE TABLE IF NOT EXISTS pre_match_context (
  pre_match_id      TEXT PRIMARY KEY,
  match_id          TEXT NOT NULL,
  team_id           TEXT NOT NULL,
  cutoff_timestamp  TEXT NOT NULL,
  feature_version   TEXT NOT NULL,
  form_last_5       TEXT,
  form_last_10      TEXT,
  goals_scored_avg  REAL,
  goals_conceded_avg REAL,
  head_to_head      TEXT,
  ranking_before    REAL,
  xg_for_avg        REAL,
  xg_against_avg    REAL,
  injuries          TEXT,
  suspensions       TEXT,
  lineup            TEXT,
  pre_match_odds    TEXT,
  source_match_ids  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pre_match_match ON pre_match_context(match_id);

CREATE TABLE IF NOT EXISTS match_snapshots (
  snapshot_id      TEXT PRIMARY KEY,
  match_id         TEXT NOT NULL,
  cutoff_seconds   INTEGER NOT NULL,
  cutoff_timestamp TEXT NOT NULL,
  snapshot_type    TEXT NOT NULL,
  information_tier TEXT NOT NULL,
  state_json       TEXT NOT NULL,
  state_hash       TEXT NOT NULL,
  validation_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_match ON match_snapshots(match_id, cutoff_seconds);

CREATE TABLE IF NOT EXISTS laya_predictions (
  prediction_id        TEXT PRIMARY KEY,
  snapshot_id           TEXT NOT NULL,
  model_version         TEXT NOT NULL,
  run_id               TEXT NOT NULL,
  raw_response_path    TEXT NOT NULL,
  raw_response_hash    TEXT NOT NULL,
  parsed_response      TEXT,
  probability_1        TEXT,
  probability_x        TEXT,
  probability_2        TEXT,
  expected_goals       REAL,
  expected_corners     REAL,
  expected_yellow_cards REAL,
  model_confidence     REAL,
  latency_ms           REAL,
  status               TEXT NOT NULL,
  error_code           TEXT
);
CREATE INDEX IF NOT EXISTS idx_predictions_run ON laya_predictions(run_id);
CREATE INDEX IF NOT EXISTS idx_predictions_snapshot ON laya_predictions(snapshot_id);

CREATE TABLE IF NOT EXISTS evaluation (
  evaluation_id          TEXT PRIMARY KEY,
  prediction_id          TEXT NOT NULL,
  actual_result          TEXT NOT NULL,
  actual_home_goals      INTEGER NOT NULL,
  actual_away_goals      INTEGER NOT NULL,
  actual_total_corners   INTEGER NOT NULL,
  actual_total_yellow_cards INTEGER NOT NULL,
  log_loss_1x2           REAL,
  brier_1x2              REAL,
  score_bucket_log_loss  REAL,
  rps_1x2                REAL,
  mae_goals              REAL,
  mae_corners            REAL,
  mae_yellow_cards       REAL,
  created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluation_prediction ON evaluation(prediction_id);
