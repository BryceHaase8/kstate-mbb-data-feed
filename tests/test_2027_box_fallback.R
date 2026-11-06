# Offline regression: multiple ESPN finals, partial bulk RDS and preserved cache.
suppressPackageStartupMessages({library(dplyr);library(readr);library(tibble)})
source("scripts/season_2027_box_fallback.R")
normalize_ids <- function(df) {
  for(k in intersect(c("athlete_id","team_id","game_id"),names(df))) df[[k]] <- as.character(df[[k]])
  df
}
event <- function(id,home,away,finished=TRUE) list(
  id=id, season=list(year=2027L,type=2L),
  competitions=list(list(status=list(type=list(completed=finished,state=if(finished)"post" else "in")),
    competitors=list(list(team=list(id="87"),score=as.character(home)),
                     list(team=list(id="222"),score=as.character(away)))))
)
make_box <- function(id,home=70,away=65) {
  tibble(season=rep(2027L,20),game_id=rep(id,20),
    team_id=rep(c("87","222"),each=10),
    athlete_id=paste0(id,"-",seq_len(20)),
    points=c(home,rep(0,9),away,rep(0,9)),
    minutes=rep(20,20), field_goals_made=rep(0,20),
    field_goals_attempted=rep(0,20), three_point_field_goals_made=rep(0,20),
    three_point_field_goals_attempted=rep(0,20), free_throws_made=rep(0,20),
    free_throws_attempted=rep(0,20), game_date=rep("2026-11-02",20),
    opponent_team_display_name=rep("Opponent",20),
    team_score=rep(c(home,away),each=10),
    starter=rep(c(TRUE,rep(FALSE,9)),2))
}
g1 <- "401920001";g2 <- "401920002";g3 <- "401920003"
dir <- tempfile("espn_2027_test_");dir.create(dir)
cache <- file.path(dir,"cache.csv.gz")
off <- function(events) function(key) list(events=events)
calls <- character()
get_box <- function(id) {calls <<- c(calls,id);make_box(id)}
a <- season_2027_box_fallback(off(list(event(g1,70,65))),get_box,
                               now="2026-11-02",cache_file=cache)
stopifnot(nrow(a)==20,length(unique(a$game_id))==1L,identical(calls,g1))
calls <- character()
b <- season_2027_box_fallback(off(list(event(g1,70,65),event(g2,70,65))),
                               get_box,now="2026-11-02",cache_file=cache)
stopifnot(nrow(b)==40,length(unique(b$game_id))==2L,identical(calls,g2))
# If ESPN corrects individual boxes but not the score, force that game to reload.
Sys.setenv(ESPN_FORCE_GAME_IDS=g2)
calls <- character()
forced <- season_2027_box_fallback(off(list(event(g1,70,65),event(g2,70,65))),
  get_box,now="2026-11-02",cache_file=cache)
stopifnot(nrow(forced)==40,identical(calls,g2))
Sys.unsetenv("ESPN_FORCE_GAME_IDS")
calls <- character()
c <- season_2027_box_fallback(off(list(event(g1,71,65),event(g2,70,65))),
   function(id) {calls <<- c(calls,id);make_box(id,if(id==g1)71 else 70)},
   now="2026-11-02",cache_file=cache)
stopifnot(nrow(c)==40,identical(calls,g1),any(c$team_score==71))
# An ESPN score mismatch must never corrupt or replace verified historical rows.
bad <- season_2027_box_fallback(off(list(event(g1,71,65),event(g2,70,65),
    event(g3,88,65))),get_box,now="2026-11-02",cache_file=cache)
stopifnot(nrow(bad)==40,!g3%in%bad$game_id)
# A partially populated bulk RDS must be augmented by new verified games.
bulk <- dplyr::bind_rows(make_box(g1,70,65),make_box(g3,55,50))
# Real hoopR bulk rows use Date; cached per-game ESPN rows use character.
bulk$game_date <- as.Date(bulk$game_date)
bulk$athlete_jersey <- rep("01",nrow(bulk))
c$athlete_jersey <- rep(1L,nrow(c))
merged <- merge_2027_player_boxes(bulk,c)
stopifnot(is.character(merged$game_date),is.character(merged$athlete_jersey))
stopifnot(nrow(merged)==60,length(unique(merged$game_id))==3L,
  all(merged$team_score[merged$game_id==g1 & merged$team_id=="87"]==71),
  sum(merged$game_id==g1)==20,sum(merged$game_id==g2)==20)
# An unresolved game outside the 21-day scan remains eligible to retry.
audit_file <- file.path(dir,"coverage.json")
writeLines('{"unresolvedByDate":{"2026-11-01":["401920004"]}}',audit_file)
days <- character()
season_2027_box_fallback(function(day) {
  days <<- c(days,day)
  list(events=list(event(g1,71,65),event(g2,70,65)))
},get_box,now="2026-12-10",cache_file=cache,audit_file=audit_file)
stopifnot("20261101" %in% days)
# Regression: two newly finalized ESPN games return different types for
# athlete_jersey. The November 5 production importer previously crashed at
# bind_rows(fetched), then silently fell back to an old bulk season file.
mixed_cache <- file.path(dir,"mixed-jersey.csv.gz")
mixed_box <- function(id) {
  box <- make_box(id)
  if(id==g1) {
    box$athlete_jersey <- rep(3L,nrow(box))
    box$game_date <- as.Date(box$game_date)
  } else {
    box$athlete_jersey <- rep("02A",nrow(box))
  }
  box
}
mixed <- season_2027_box_fallback(
  off(list(event(g1,70,65),event(g2,70,65))),
  mixed_box,now="2026-11-02",cache_file=mixed_cache)
stopifnot(nrow(mixed)==40L,identical(sort(unique(mixed$game_id)),sort(c(g1,g2))),
  is.character(mixed$athlete_jersey),is.character(mixed$game_date),
  all(mixed$athlete_jersey[mixed$game_id==g1]=="3"),
  all(mixed$athlete_jersey[mixed$game_id==g2]=="02A"))
mixed_next <- season_2027_box_fallback(
  off(list(event(g1,70,65),event(g2,70,65),event(g3,70,65))),
  mixed_box,now="2026-11-02",cache_file=mixed_cache)
stopifnot(nrow(mixed_next)==60L,length(unique(mixed_next$game_id))==3L,
  is.character(mixed_next$athlete_jersey))
unlink(dir,recursive=TRUE)
cat("PASS: verified ESPN games supplement partial hoopR, cache is preserved, corrections rechecked\n")
