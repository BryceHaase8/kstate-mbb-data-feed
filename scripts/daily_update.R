# ============================================================
# DAILY D-I FACTUAL DATA UPDATE
#
# Downloads only one season of ESPN/hoopR player-box data,
# restricts it to the ESPN Division I team universe,
# rebuilds clean player-season stats, then writes the public JSON.
#
# Season behavior:
# - If TARGET_SEASON is provided, use it.
# - Otherwise use the likely current NCAA ending year.
# - If that season has no player box rows yet, fall back one year.
# ============================================================

packages <- c(
  "hoopR", "dplyr", "readr", "purrr", "stringr", "tibble", "jsonlite"
)

missing <- packages[!(packages %in% rownames(installed.packages()))]
if (length(missing) > 0) install.packages(missing)

library(hoopR)
library(dplyr)
library(readr)
library(purrr)
library(stringr)
library(tibble)
library(jsonlite)

season_label <- function(year) {
  paste0(year - 1, "-", substr(as.character(year), 3, 4))
}

sum0 <- function(x) sum(as.numeric(x), na.rm = TRUE)

rate <- function(num, den) {
  ifelse(is.na(den) | den == 0, NA_real_, num / den)
}

first_nonmissing <- function(x) {
  good <- !is.na(x) & as.character(x) != ""
  if (!any(good)) return(NA)
  x[which(good)[1]]
}

normalize_ids <- function(df) {
  id_cols <- names(df)[
    stringr::str_detect(
      names(df),
      "(^|_)athlete_id($|_)|(^|_)team_id($|_)|^game_id$"
    )
  ]
  if (length(id_cols) > 0) {
    df <- df %>%
      mutate(across(all_of(id_cols), as.character))
  }
  df
}

ensure_column <- function(df, name, value = NA) {
  if (!(name %in% names(df))) df[[name]] <- value
  df
}

derive_candidate_season <- function() {
  today <- Sys.Date()
  y <- as.integer(format(today, "%Y"))
  m <- as.integer(format(today, "%m"))
  if (m >= 7) y + 1L else y
}

target_override <- trimws(Sys.getenv("TARGET_SEASON", unset = ""))
candidate <- if (target_override != "") {
  as.integer(target_override)
} else {
  derive_candidate_season()
}

cat("Candidate season:", candidate, "(", season_label(candidate), ")\n")

try_load_player_box <- function(year) {
  tryCatch(
    hoopR::load_mbb_player_box(seasons = year) %>%
      as_tibble() %>%
      normalize_ids(),
    error = function(e) {
      message("Player-box load failed for ", year, ": ", conditionMessage(e))
      tibble()
    }
  )
}

player_box_raw <- try_load_player_box(candidate)

if (nrow(player_box_raw) == 0 && target_override == "") {
  candidate <- candidate - 1L
  cat("No rows yet. Falling back to:", candidate, "(", season_label(candidate), ")\n")
  player_box_raw <- try_load_player_box(candidate)
}

if (nrow(player_box_raw) == 0) {
  stop("No player-box rows available. Existing public feed should remain unchanged.")
}

# ------------------------------------------------------------
# ESPN Division I team universe
# ------------------------------------------------------------

children <- hoopR::espn_mbb_season_group_children(
  group_id = 50,
  season = candidate,
  season_type = 2
) %>%
  as_tibble()

if (nrow(children) == 0 || !("child_group_id" %in% names(children))) {
  stop("Could not retrieve ESPN Division I conference groups.")
}

group_ids <- unique(as.character(children$child_group_id))
group_ids <- group_ids[!is.na(group_ids) & group_ids != ""]

d1_teams <- purrr::map_dfr(
  group_ids,
  function(group_id) {
    x <- tryCatch(
      hoopR::espn_mbb_season_group_teams(
        group_id = group_id,
        season = candidate,
        season_type = 2
      ),
      error = function(e) NULL
    )
    if (is.null(x) || nrow(x) == 0) return(tibble())

    as_tibble(x) %>%
      transmute(
        season = as.integer(candidate),
        espn_team_id = as.character(team_id)
      )
  }
) %>%
  filter(!is.na(espn_team_id), espn_team_id != "") %>%
  distinct(season, espn_team_id)

team_count <- n_distinct(d1_teams$espn_team_id)

if (team_count < 340 || team_count > 400) {
  stop(paste("Safety stop: ESPN D-I team count looks wrong:", team_count))
}

# ------------------------------------------------------------
# Keep only D-I player rows
# ------------------------------------------------------------

player_box <- player_box_raw %>%
  inner_join(
    d1_teams,
    by = c("season" = "season", "team_id" = "espn_team_id")
  )

if (nrow(player_box) == 0) {
  stop("D-I filter returned zero player-box rows.")
}

# Correct games-played logic.
activity_cols <- intersect(
  c(
    "field_goals_made","field_goals_attempted",
    "three_point_field_goals_made","three_point_field_goals_attempted",
    "free_throws_made","free_throws_attempted",
    "offensive_rebounds","defensive_rebounds","rebounds",
    "assists","steals","blocks","turnovers","fouls","points"
  ),
  names(player_box)
)

player_box <- ensure_column(player_box, "did_not_play", NA)
player_box <- ensure_column(player_box, "starter", FALSE)
player_box <- ensure_column(player_box, "minutes", NA_real_)

player_box <- player_box %>%
  mutate(
    stat_activity =
      if (length(activity_cols) > 0) {
        rowSums(
          across(
            all_of(activity_cols),
            ~ coalesce(as.numeric(.x), 0)
          ),
          na.rm = TRUE
        )
      } else {
        0
      },

    played = case_when(
      !is.na(did_not_play) ~ !as.logical(did_not_play),
      coalesce(as.logical(starter), FALSE) ~ TRUE,
      coalesce(as.numeric(minutes), 0) > 0 ~ TRUE,
      stat_activity > 0 ~ TRUE,
      TRUE ~ FALSE
    )
  ) %>%
  select(-stat_activity)

required_stats <- c(
  "field_goals_made","field_goals_attempted",
  "three_point_field_goals_made","three_point_field_goals_attempted",
  "free_throws_made","free_throws_attempted",
  "offensive_rebounds","defensive_rebounds","rebounds",
  "assists","steals","blocks","turnovers","fouls","points","minutes"
)

for (nm in required_stats) {
  player_box <- ensure_column(player_box, nm, NA_real_)
}

for (nm in c(
  "athlete_display_name",
  "athlete_position_abbreviation",
  "athlete_jersey",
  "athlete_headshot_href",
  "team_display_name",
  "game_id"
)) {
  player_box <- ensure_column(player_box, nm, NA_character_)
}

# ------------------------------------------------------------
# Aggregate one row per athlete/team/season
# ------------------------------------------------------------

stats <- player_box %>%
  filter(
    played,
    !is.na(athlete_id),
    athlete_id != "",
    !is.na(team_id),
    team_id != ""
  ) %>%
  group_by(season, athlete_id, team_id) %>%
  summarise(
    player_name = first_nonmissing(athlete_display_name),
    team_name = first_nonmissing(team_display_name),
    position = first_nonmissing(athlete_position_abbreviation),
    jersey = first_nonmissing(athlete_jersey),
    headshot = first_nonmissing(athlete_headshot_href),

    gp = n_distinct(game_id),
    gs = sum(coalesce(as.logical(starter), FALSE), na.rm = TRUE),
    minutes = sum0(minutes),

    fgm = sum0(field_goals_made),
    fga = sum0(field_goals_attempted),
    three_pm = sum0(three_point_field_goals_made),
    three_pa = sum0(three_point_field_goals_attempted),
    ftm = sum0(free_throws_made),
    fta = sum0(free_throws_attempted),

    oreb = sum0(offensive_rebounds),
    dreb = sum0(defensive_rebounds),
    reb = sum0(rebounds),
    ast = sum0(assists),
    stl = sum0(steals),
    blk = sum0(blocks),
    tov = sum0(turnovers),
    pf = sum0(fouls),
    pts = sum0(points),

    .groups = "drop"
  ) %>%
  mutate(
    season_label = season_label(as.integer(season)),
    two_pm = fgm - three_pm,
    two_pa = fga - three_pa,

    mpg = rate(minutes, gp),
    ppg = rate(pts, gp),
    rpg = rate(reb, gp),
    apg = rate(ast, gp),
    spg = rate(stl, gp),
    bpg = rate(blk, gp),
    topg = rate(tov, gp),

    fg_pct = rate(fgm, fga),
    two_pt_pct = rate(two_pm, two_pa),
    three_pt_pct = rate(three_pm, three_pa),
    ft_pct = rate(ftm, fta),
    efg_pct = rate(fgm + 0.5 * three_pm, fga),
    ts_pct = rate(pts, 2 * (fga + 0.44 * fta)),
    ast_to = rate(ast, tov),

    two_pa_pg = rate(two_pa, gp),
    three_pa_pg = rate(three_pa, gp),
    fta_pg = rate(fta, gp),
    two_attempt_share = rate(two_pa, two_pa + three_pa),
    three_attempt_share = rate(three_pa, two_pa + three_pa)
  ) %>%
  select(
    season, season_label, athlete_id, player_name, team_id, team_name,
    position, jersey, headshot,
    gp, gs, minutes, mpg,
    pts, ppg, reb, rpg, ast, apg, stl, spg, blk, bpg, tov, topg, pf,
    fgm, fga, fg_pct,
    two_pm, two_pa, two_pt_pct,
    three_pm, three_pa, three_pt_pct,
    ftm, fta, ft_pct,
    oreb, dreb,
    efg_pct, ts_pct, ast_to,
    two_pa_pg, three_pa_pg, fta_pg,
    two_attempt_share, three_attempt_share
  ) %>%
  arrange(team_name, desc(ppg), player_name)

# Multiple-team rows can exist for transfer mid-season situations.
# The public feed must still have one ESPN athlete ID key.
# Keep the row with the most games for the current feed.
stats <- stats %>%
  arrange(athlete_id, desc(gp), desc(minutes)) %>%
  distinct(athlete_id, .keep_all = TRUE)

# Early-season player count may legitimately be small.
# For completed/established seasons, protect against a catastrophic partial feed.
if (nrow(stats) < 20) {
  stop(
    paste0(
      "Safety stop: only ",
      nrow(stats),
      " D-I players were produced."
    )
  )
}

dir.create("data", showWarnings = FALSE, recursive = TRUE)
write_csv(stats, file.path("data", "current_player_season_stats.csv"))

# Build the public JSON.
source(file.path("scripts", "build_public_factual_json.R"))

cat("\nDaily update complete.\n")
cat("Season:", candidate, "\n")
cat("D-I teams:", team_count, "\n")
cat("Players:", nrow(stats), "\n")
