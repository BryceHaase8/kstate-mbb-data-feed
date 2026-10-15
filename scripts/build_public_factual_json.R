# ============================================================
# BUILD PUBLIC PORTAL FACTUAL JSON
#
# Reads:
#   data/current_player_season_stats.csv
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
  filter(
    !is.na(athlete_id),
    athlete_id != ""
  ) %>%
  distinct(
    athlete_id,
    .keep_all = TRUE
  )

if (nrow(stats) < 1000) {
  stop(
    paste0(
      "Safety stop: only ",
      nrow(stats),
      " player rows are present. Refusing to publish."
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

players <- list()

for (i in seq_len(nrow(stats))) {

  row <- stats[i, ]
  athlete_id <- as.character(row$athlete_id[[1]])

  rec <- list(
    espnAthleteId = athlete_id,
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

  players[[athlete_id]] <- rec
}

season_value <- max(
  suppressWarnings(as.integer(stats$season)),
  na.rm = TRUE
)

season_label_value <- stats$season_label[
  which(!is.na(stats$season_label) & stats$season_label != "")[1]
]

payload <- list(
  schemaVersion = 1,
  generatedAt = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
  season = season_value,
  seasonLabel = ifelse(length(season_label_value) == 0, NA, season_label_value),
  playerCount = length(players),
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
cat("Season:", payload$season, "\n")
cat("Players:", payload$playerCount, "\n")
cat("Size MB:", round(file.info(OUTPUT_FILE)$size / 1024^2, 2), "\n")
