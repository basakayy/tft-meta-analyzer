-- One row per match
CREATE TABLE IF NOT EXISTS matches (
    match_id      TEXT PRIMARY KEY,
    game_datetime BIGINT NOT NULL,            -- Unix time in milliseconds
    game_length   DOUBLE PRECISION NOT NULL,  -- seconds
    set_number    INTEGER NOT NULL,
    queue_id      INTEGER NOT NULL,
    game_version  TEXT NOT NULL
);

-- One row per player in a match; player identity is not stored
CREATE TABLE IF NOT EXISTS participants (
    participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id       TEXT NOT NULL REFERENCES matches (match_id),
    placement      INTEGER NOT NULL,
    level          INTEGER NOT NULL
);

-- One row per unit on a player's final board
CREATE TABLE IF NOT EXISTS units (
    unit_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    participant_id BIGINT NOT NULL REFERENCES participants (participant_id),
    character_id   TEXT NOT NULL,
    star_level     INTEGER NOT NULL,
    rarity         INTEGER NOT NULL
);

-- One row per trait on a player's final board
CREATE TABLE IF NOT EXISTS traits (
    trait_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    participant_id BIGINT NOT NULL REFERENCES participants (participant_id),
    name           TEXT NOT NULL,
    num_units      INTEGER NOT NULL,
    style          INTEGER NOT NULL,  -- 0 means the trait is not active
    tier_current   INTEGER NOT NULL
);

-- One row per item equipped on a unit
CREATE TABLE IF NOT EXISTS items (
    item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unit_id BIGINT NOT NULL REFERENCES units (unit_id),
    name    TEXT NOT NULL
);

-- Indexes speed up lookups on the columns used to join and filter
CREATE INDEX IF NOT EXISTS idx_participants_match ON participants (match_id);
CREATE INDEX IF NOT EXISTS idx_units_participant ON units (participant_id);
CREATE INDEX IF NOT EXISTS idx_traits_participant ON traits (participant_id);
CREATE INDEX IF NOT EXISTS idx_items_unit ON items (unit_id);
