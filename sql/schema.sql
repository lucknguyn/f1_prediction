-- Generated from SQLAlchemy models; MySQL 8.4+
-- Select an empty database before running.
SET NAMES utf8mb4;

CREATE TABLE circuits (
	id VARCHAR(80) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	country VARCHAR(80), 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE drivers (
	id VARCHAR(80) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	code VARCHAR(10), 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ingestion_runs (
	id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	source VARCHAR(120) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE model_runs (
	id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	train_through DATETIME NOT NULL, 
	split VARCHAR(32) NOT NULL, 
	artifact VARCHAR(512), 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE teams (
	id VARCHAR(80) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE races (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	season INTEGER NOT NULL, 
	round INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	circuit_id VARCHAR(80) NOT NULL, 
	start_utc DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (season, round), 
	CHECK (round > 0), 
	FOREIGN KEY(circuit_id) REFERENCES circuits (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_races_season ON races (season);

CREATE INDEX ix_races_start_utc ON races (start_utc);

CREATE TABLE entries (
	race_id INTEGER NOT NULL, 
	driver_id VARCHAR(80) NOT NULL, 
	team_id VARCHAR(80) NOT NULL, 
	PRIMARY KEY (race_id, driver_id), 
	FOREIGN KEY(race_id) REFERENCES races (id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (id), 
	FOREIGN KEY(team_id) REFERENCES teams (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE evaluation_metrics (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	run_id VARCHAR(36) NOT NULL, 
	race_id INTEGER, 
	name VARCHAR(64) NOT NULL, 
	value FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_id) REFERENCES model_runs (id), 
	FOREIGN KEY(race_id) REFERENCES races (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_evaluation_metrics_run_id ON evaluation_metrics (run_id);

CREATE TABLE sessions (
	id VARCHAR(24) NOT NULL, 
	race_id INTEGER NOT NULL, 
	kind VARCHAR(4) NOT NULL, 
	exported_at DATETIME NOT NULL, 
	source VARCHAR(120) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (race_id, kind), 
	UNIQUE (race_id, id), 
	FOREIGN KEY(race_id) REFERENCES races (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE feature_snapshots (
	id VARCHAR(64) NOT NULL, 
	race_id INTEGER NOT NULL, 
	driver_id VARCHAR(80) NOT NULL, 
	cutoff_utc DATETIME NOT NULL, 
	version VARCHAR(32) NOT NULL, 
	features JSON NOT NULL, 
	label INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(race_id, driver_id) REFERENCES entries (race_id, driver_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_feature_snapshots_race_id ON feature_snapshots (race_id);

CREATE TABLE session_results (
	session_id VARCHAR(24) NOT NULL, 
	driver_id VARCHAR(80) NOT NULL, 
	race_id INTEGER NOT NULL, 
	position INTEGER, 
	q1_seconds FLOAT, 
	q2_seconds FLOAT, 
	q3_seconds FLOAT, 
	points FLOAT, 
	status VARCHAR(120), 
	PRIMARY KEY (session_id, driver_id), 
	FOREIGN KEY(race_id, session_id) REFERENCES sessions (race_id, id), 
	FOREIGN KEY(race_id, driver_id) REFERENCES entries (race_id, driver_id), 
	CHECK (position IS NULL OR position > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_session_results_race_id ON session_results (race_id);

CREATE TABLE weather_observations (
	session_id VARCHAR(24) NOT NULL, 
	elapsed_seconds FLOAT NOT NULL, 
	air_temp FLOAT, 
	track_temp FLOAT, 
	humidity FLOAT, 
	wind_speed FLOAT, 
	rainfall INTEGER, 
	PRIMARY KEY (session_id, elapsed_seconds), 
	FOREIGN KEY(session_id) REFERENCES sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE predictions (
	run_id VARCHAR(36) NOT NULL, 
	snapshot_id VARCHAR(64) NOT NULL, 
	score FLOAT NOT NULL, 
	`rank` INTEGER NOT NULL, 
	PRIMARY KEY (run_id, snapshot_id), 
	CHECK (`rank` > 0), 
	FOREIGN KEY(run_id) REFERENCES model_runs (id), 
	FOREIGN KEY(snapshot_id) REFERENCES feature_snapshots (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE OR REPLACE VIEW prediction_comparison AS
        SELECT m.id AS run_id, m.name AS model, m.split, r.season, r.round,
               r.name AS race, d.name AS driver, t.name AS team,
               p.score, p.rank AS predicted_rank, f.label AS actual_rank
        FROM predictions p JOIN model_runs m ON m.id = p.run_id
        JOIN feature_snapshots f ON f.id = p.snapshot_id
        JOIN races r ON r.id = f.race_id JOIN drivers d ON d.id = f.driver_id
        JOIN entries e ON e.race_id = f.race_id AND e.driver_id = f.driver_id
        JOIN teams t ON t.id = e.team_id;
