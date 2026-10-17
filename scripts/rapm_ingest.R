# Research-only: fetch a single active NCAA season, not four years daily.
suppressPackageStartupMessages({library(hoopR);library(dplyr);library(readr)})
season <- as.integer(Sys.getenv("TARGET_SEASON", ""))
if (is.na(season)) {
  today <- Sys.Date()
  season <- as.integer(format(today,"%Y")) + ifelse(as.integer(format(today,"%m"))>=7,1L,0L)
}
message("RAPM ingest NCAA ending year: ",season)
dir.create("rapm_input",showWarnings=FALSE)
load_safe <- function(fn) tryCatch(fn(seasons=season),error=function(e){message("hoopR no data: ",conditionMessage(e));tibble()})
pbp <- load_safe(hoopR::load_mbb_pbp)
box <- load_safe(hoopR::load_mbb_player_box)
# Normalize raw hoopR MBB columns to the previously validated internal PBP schema.
# The upstream source stores "type_text", "clock_minutes/clock_seconds"
# and "participants_0_athlete_id"; our lineup engine expects normalized names.
if (!"event_type" %in% names(pbp) && "type_text" %in% names(pbp)) {
  raw_type <- as.character(pbp$type_text)
  pbp$event_type <- dplyr::case_when(
    grepl("Shot$",raw_type) ~ "2PT Shot",
    grepl("Rebound$",raw_type) ~ "Rebound",
    grepl("Turnover$",raw_type) ~ "Turnover",
    grepl("Foul$",raw_type) ~ "Foul",
    grepl("TimeOut$",raw_type) ~ "Timeout",
    TRUE ~ raw_type
  )
}
if (!"seconds_remaining_period" %in% names(pbp)) {
  if (all(c("clock_minutes","clock_seconds") %in% names(pbp))) {
    pbp$seconds_remaining_period <-
      suppressWarnings(as.numeric(pbp$clock_minutes))*60 +
      suppressWarnings(as.numeric(pbp$clock_seconds))
  } else if ("start_quarter_seconds_remaining" %in% names(pbp)) {
    pbp$seconds_remaining_period <-
      suppressWarnings(as.numeric(pbp$start_quarter_seconds_remaining))
  }
}
if (!"athlete_id_1" %in% names(pbp) &&
    "participants_0_athlete_id" %in% names(pbp))
  pbp$athlete_id_1 <- as.character(pbp$participants_0_athlete_id)
# Shot outcome in raw ESPN PBP can be derived without assuming every shot
# with a missing flag was made.
if (!"shot_made" %in% names(pbp))
  pbp$shot_made <- ifelse(as.character(pbp$event_type)=="2PT Shot",
                         grepl(" makes | made ",paste0(" ",tolower(as.character(pbp$text))," ")),
                         NA)

need_pbp <- c("game_id","period_number","seconds_remaining_period","home_team_id","away_team_id", "team_id", "event_type","text","home_score","away_score","athlete_id_1")
need_box <- c("game_id","team_id","athlete_id","starter","minutes")
if (!nrow(pbp) || !nrow(box)) {
  message("No completed season data yet. Leaving any prior successful RAPM publish untouched.")
  quit(save="no",status=0)
}
missing_pbp <- setdiff(need_pbp,names(pbp)); missing_box <- setdiff(need_box,names(box))
if (length(missing_pbp) || length(missing_box)) stop(paste("Required columns missing: PBP",paste(missing_pbp,collapse=","),"box",paste(missing_box,collapse=",")))
optional_pbp <- c("season","sequence_number","shot_made","shot_value","score_value")
for (n in optional_pbp) if (!n %in% names(pbp)) pbp[[n]] <- NA
pbp <- pbp %>% mutate(game_id=as.character(game_id), across(any_of(c("home_team_id","away_team_id","team_id","athlete_id_1")),as.character),
  period_number=as.integer(period_number),seconds_remaining_period=as.numeric(seconds_remaining_period),
  sequence_sort=suppressWarnings(as.numeric(sequence_number))) %>%
  filter(!is.na(game_id), !is.na(period_number), !is.na(seconds_remaining_period)) %>%
  arrange(game_id,period_number,desc(seconds_remaining_period)) %>% select(all_of(unique(c(need_pbp, optional_pbp))))
box <- box %>% mutate(across(any_of(c("game_id","team_id","athlete_id")),as.character)) %>%
  select(any_of(c(need_box,"points","field_goals_attempted","offensive_rebounds","turnovers","free_throws_attempted")))
# Keep only games that have official box rows for both teams and a second-half event.
complete <- box %>% filter(!is.na(team_id)) %>% count(game_id) %>% filter(n>=10) %>% pull(game_id)
has_final <- pbp %>% filter(event_type=="End Game") %>% pull(game_id) %>% unique()
games <- intersect(complete,has_final)
pbp <- pbp %>% filter(game_id %in% games)
box <- box %>% filter(game_id %in% games)
write_csv(pbp,"rapm_input/pbp.csv",na="")
write_csv(box,"rapm_input/box.csv",na="")
message("RAPM ingest complete games candidate: ",length(games),"; events: ",nrow(pbp))
