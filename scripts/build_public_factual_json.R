# ============================================================
# BUILD PUBLIC PORTAL FACTUAL JSON — MULTI-SEASON
#
# Reads:
#   data/current_player_season_stats.csv
#
# The CSV name is retained for compatibility, but the file now
# stores every preserved season (starting with 2022-23).
#
# Writes:
#   public/portal_factual_data.json
#
# Contains factual basketball information only.
# No Portal membership, ratings, notes, board rank, NIL intel,
# agents, colors, categories, or staff-entered data.
# ============================================================

packages <- c("readr", "dplyr", "jsonlite")
missing <- packages[!(packages %in% rownames(installed.packages()))]
if (length(missing) > 0) install.packages(missing)

library(readr)
library(dplyr)
library(jsonlite)

DATA_FILE <- file.path("data", "current_player_season_stats.csv")
OUTPUT_FILE <- file.path("public", "portal_factual_data.json")

if (!file.exists(DATA_FILE)) {
  stop(paste("Missing:", DATA_FILE))
}

stats <- read_csv(
  DATA_FILE,
  col_types = cols(.default = col_character()),
  show_col_types = FALSE
)

required <- c(
  "season", "season_label", "athlete_id", "player_name",
  "team_id", "team_name", "position", "jersey", "headshot"
)

missing_cols <- setdiff(required, names(stats))
if (length(missing_cols) > 0) {
  stop(paste("Missing columns:", paste(missing_cols, collapse = ", ")))
}

numeric_fields <- c(
  "gp","gs","minutes","mpg","pts","ppg","reb","rpg","ast","apg",
  "stl","spg","blk","bpg","tov","topg","pf","fgm","fga","fg_pct",
  "two_pm","two_pa","two_pt_pct","three_pm","three_pa","three_pt_pct",
  "ftm","fta","ft_pct","oreb","dreb","efg_pct","ts_pct","ast_to",
  "two_pa_pg","three_pa_pg","fta_pg","two_attempt_share",
  "three_attempt_share"
)

for (nm in numeric_fields) {
  if (!(nm %in% names(stats))) stats[[nm]] <- NA_character_
}

stats <- stats %>%
  mutate(
    season_num = suppressWarnings(as.integer(season))
  ) %>%
  filter(
    !is.na(athlete_id),
    athlete_id != "",
    !is.na(season_num)
  ) %>%
  arrange(athlete_id, season_num) %>%
  distinct(season_num, athlete_id, .keep_all = TRUE)

season_values <- sort(unique(stats$season_num))

if (length(season_values) < 4) {
  stop(
    paste0(
      "Safety stop: expected at least 4 seasons, found ",
      length(season_values),
      ": ",
      paste(season_values, collapse = ", ")
    )
  )
}

if (nrow(stats) < 15000) {
  stop(
    paste0(
      "Safety stop: only ",
      nrow(stats),
      " player-season rows are present. Refusing to publish."
    )
  )
}

num_or_null <- function(x) {
  v <- suppressWarnings(as.numeric(x))
  if (length(v) == 0 || is.na(v) || !is.finite(v)) return(NULL)
  v
}

char_or_null <- function(x) {
  if (length(x) == 0 || is.na(x) || trimws(as.character(x)) == "") return(NULL)
  as.character(x)
}

make_season_record <- function(row) {
  rec <- list(
    season = suppressWarnings(as.integer(row$season[[1]])),
    seasonLabel = char_or_null(row$season_label[[1]]),
    name = char_or_null(row$player_name[[1]]),
    teamId = char_or_null(row$team_id[[1]]),
    team = char_or_null(row$team_name[[1]]),
    position = char_or_null(row$position[[1]]),
    jersey = char_or_null(row$jersey[[1]]),
    headshot = char_or_null(row$headshot[[1]])
  )

  for (field in numeric_fields) {
    rec[[field]] <- num_or_null(row[[field]][[1]])
  }

  rec
}

player_groups <- split(stats, stats$athlete_id)

players <- lapply(
  names(player_groups),
  function(athlete_id) {
    player_rows <- player_groups[[athlete_id]] %>%
      arrange(season_num)

    seasons <- lapply(
      seq_len(nrow(player_rows)),
      function(i) make_season_record(player_rows[i, ])
    )

    list(
      espnAthleteId = as.character(athlete_id),
      latest = seasons[[length(seasons)]],
      seasons = seasons
    )
  }
)

names(players) <- names(player_groups)

latest_season <- max(season_values)

latest_label_values <- stats %>%
  filter(season_num == latest_season) %>%
  pull(season_label)

latest_label_values <- latest_label_values[
  !is.na(latest_label_values) & latest_label_values != ""
]

season_counts <- stats %>%
  count(season_num, name = "players") %>%
  arrange(season_num)

season_player_counts <- as.list(season_counts$players)
names(season_player_counts) <- as.character(season_counts$season_num)

payload <- list(
  schemaVersion = 2,
  generatedAt = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
  latestSeason = latest_season,
  seasonLabel = if (length(latest_label_values) > 0) latest_label_values[[1]] else NULL,
  seasonCount = length(season_values),
  seasons = season_values,
  playerSeasonCount = nrow(stats),
  playerCount = length(players),
  seasonPlayerCounts = season_player_counts,
  scope = "NCAA Division I men's basketball factual data only",
  players = players
)

dir.create("public", showWarnings = FALSE, recursive = TRUE)

write_json(
  payload,
  OUTPUT_FILE,
  auto_unbox = TRUE,
  pretty = FALSE,
  na = "null",
  null = "null",
  digits = NA
)

cat("\nBuilt:", OUTPUT_FILE, "\n")
cat("Seasons:", paste(season_values, collapse = ", "), "\n")
cat("Player-seasons:", payload$playerSeasonCount, "\n")
cat("Unique players:", payload$playerCount, "\n")
cat("Size MB:", round(file.info(OUTPUT_FILE)$size / 1024^2, 2), "\n")
