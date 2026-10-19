#!/usr/bin/env Rscript
# RESEARCH BRANCH ONLY. One-time historical NCAA MBB ESPN box + game-log + PBP backfill.
# 2020=2019-20, 2026=2025-26. ESPN IDs and player-game facts are public,
# and no staff information is read. Production feed is not changed.
suppressPackageStartupMessages({
 library(hoopR); library(dplyr); library(readr); library(tibble)
 library(purrr); library(stringr); library(jsonlite)
})
run_mode <- tolower(Sys.getenv("BACKFILL_MODE","all"))
stopifnot(run_mode %in% c("all","box","pbp"))
start_year <- as.integer(Sys.getenv("BACKFILL_FIRST_SEASON","2020"))
end_year <- as.integer(Sys.getenv("BACKFILL_LAST_SEASON","2026"))
if(is.na(start_year)||is.na(end_year)||start_year<2020||end_year>2026||start_year>end_year)
  stop("Unsafe date range. Backfill only 2020–2026 ending years.")
pilot <- identical(Sys.getenv("BACKFILL_PILOT","0"),"1")
if(pilot) {start_year <- 2022L;end_year <- 2022L}
years <- seq.int(start_year,end_year)
outroot <- "research_data/historical"
dir.create(outroot,recursive=TRUE,showWarnings=FALSE)
dir.create("research_qa/historical",recursive=TRUE,showWarnings=FALSE)
archive_dir <- function(part) {p<-file.path(outroot,part);dir.create(p,recursive=TRUE,showWarnings=FALSE);p}
save_gz_csv <- function(df,path) {
 c <- gzfile(path,"wb")
 on.exit(close(c),add=TRUE)
 utils::write.csv(df,c,row.names=FALSE,na="")
 if(!file.exists(path)) stop("Failed archive ",path)
}
save_json <- function(x,path) jsonlite::write_json(x,path,pretty=TRUE,auto_unbox=TRUE,na="null")
log_line <- function(...) cat(sprintf("[%s] ",format(Sys.time(),"%Y-%m-%d %H:%M:%S UTC",tz="UTC")), ..., "\n")
assert_unique <- function(df,keys,label){
  if(nrow(df)!=nrow(distinct(df,across(all_of(keys)))))
    stop(paste("Duplicate key in",label,paste(keys,collapse=",")))
}
# Reuse EXACT production aggregation definitions without executing daily_update.R.
# Stop parsing at active-season execution; no main-feed mutation.
load_production_aggregator <- function() {
 lines <- readLines("scripts/daily_update.R",warn=FALSE)
 boundary <- grep("^# Resolve active season",lines)
 if(length(boundary)!=1) stop("Production aggregate boundary changed; audit before running")
 preamble <- paste(lines[seq_len(boundary[1]-1L)],collapse="\n")
 eval(parse(text=preamble),envir=.GlobalEnv)
 if(!exists("build_season_stats",mode="function") ||
    !exists("get_d1_teams",mode="function")) stop("Missing production aggregation functions")
}
load_production_aggregator()
num <- function(x){suppressWarnings(as.numeric(x))}
ensure <- function(df,nm,val=NA) {if(!nm %in% names(df)) df[[nm]] <- val;df}
norm <- function(x) {x<-as.character(x);x[is.na(x)]<-"";x}
raw_box <- function(year) {
 log_line("Retrieving hoopR ESPN player boxes for NCAA ending year ",year)
 b <- tryCatch(hoopR::load_mbb_player_box(seasons=year)%>%as_tibble(),error=function(e)stop("Player-box fetch ",year,": ",conditionMessage(e)))
 required<-c("athlete_id","team_id","game_id","season","minutes","points","field_goals_attempted")
 absent<-setdiff(required,names(b))
 if(length(absent)) stop(paste("ESPN box schema missing",paste(absent,collapse=","),year))
 b<-normalize_ids(b)
 b$season<-as.integer(b$season)
 b<-b%>%filter(season==year,!is.na(game_id),game_id!="",!is.na(team_id),team_id!="",
              !is.na(athlete_id),athlete_id!="")
 if(nrow(b)<30000) stop("Implausibly few player-game rows in ",year,": ",nrow(b))
 d1<-get_d1_teams(year)
 filtered<-b%>%semi_join(d1,by=c("season"="season","team_id"="espn_team_id"))
 if(nrow(filtered)<30000) stop("D-I filter removed too much ",year," rows ",nrow(filtered))
 log_line(year," raw rows ",nrow(b)," D1 raw ",nrow(filtered),
          " teams ",n_distinct(filtered$team_id)," games ",n_distinct(filtered$game_id))
 filtered
}
# Standard event-free game log archive, accessible later for the user-facing Game Logs
# view without loading it on every Players-page visit.
make_game_logs <- function(b,year) {
 for(n in c("did_not_play","starter","game_date","game_date_time",
             "athlete_display_name","athlete_position_abbreviation",
             "team_display_name","opponent_team_id",
             "opponent_team_display_name","home_away","team_score","opponent_team_score"))
   b<-ensure(b,n)
 stats<-c("minutes","points","rebounds","assists","steals","blocks","turnovers",
          "fouls","offensive_rebounds","defensive_rebounds","field_goals_made",
          "field_goals_attempted","three_point_field_goals_made",
          "three_point_field_goals_attempted","free_throws_made",
          "free_throws_attempted")
 for(n in stats)b<-ensure(b,n)
 b<-b%>%mutate(
   played=case_when(!is.na(did_not_play)~!as.logical(did_not_play),
            coalesce(as.logical(starter),FALSE)~TRUE,
            coalesce(num(minutes),0)>0~TRUE,
            coalesce(num(points),0)+coalesce(num(rebounds),0)+
             coalesce(num(assists),0)+coalesce(num(field_goals_attempted),0)>0~TRUE,
            TRUE~FALSE),
   team_id=as.character(team_id),athlete_id=as.character(athlete_id),game_id=as.character(game_id)
 )%>%filter(played)%>%
 transmute(
  season=as.integer(season), game_id, game_date=as.character(game_date),
  athlete_id, player_name=as.character(athlete_display_name),
  team_id,team_name=as.character(team_display_name),
  opponent_team_id=as.character(opponent_team_id),
  opponent_team=as.character(opponent_team_display_name),
  home_away=as.character(home_away),
  team_score=num(team_score),opponent_score=num(opponent_team_score),
  started=coalesce(as.logical(starter),FALSE),
  minutes=num(minutes),points=num(points),rebounds=num(rebounds),assists=num(assists),
  steals=num(steals),blocks=num(blocks),turnovers=num(turnovers),fouls=num(fouls),
  offensive_rebounds=num(offensive_rebounds),defensive_rebounds=num(defensive_rebounds),
  fgm=num(field_goals_made),fga=num(field_goals_attempted),
  three_pm=num(three_point_field_goals_made),
  three_pa=num(three_point_field_goals_attempted),
  ftm=num(free_throws_made),fta=num(free_throws_attempted)
 )%>%arrange(game_date,game_id,team_id,athlete_id)
 assert_unique(b,c("game_id","team_id","athlete_id"),paste(year,"player-game"))
 b
}
box_qa<-list()
for (year in if(run_mode %in% c("all","box")) years else integer()) {
 b<-raw_box(year)
 logs<-make_game_logs(b,year)
 season_summary<-build_season_stats(year,player_box_raw=b)
 if(nrow(season_summary)<3500) stop(year," produced too few D1 player seasons: ",nrow(season_summary))
 assert_unique(season_summary,c("season","athlete_id"),"season totals")
 file_logs<-file.path(archive_dir("game_logs"),paste0("player_game_logs_",year,".csv.gz"))
 file_seas<-file.path(archive_dir("season_totals"),paste0("player_season_",year,".csv.gz"))
 save_gz_csv(logs,file_logs)
 save_gz_csv(season_summary,file_seas)
 qa<-list(season=year,player_game_rows=nrow(logs),unique_games=n_distinct(logs$game_id),
     unique_teams=n_distinct(logs$team_id),unique_athletes=n_distinct(logs$athlete_id),
     season_rows=nrow(season_summary),game_log_size_bytes=file.info(file_logs)$size,
     season_file_size_bytes=file.info(file_seas)$size,
     source="hoopR ESPN player-game box with production D1 and season-stat aggregator",
     no_roster_only_claim=TRUE)
 save_json(qa,file.path("research_qa/historical",paste0("box_qa_",year,".json")))
 box_qa[[as.character(year)]]<-qa
 log_line("ARCHIVED BOX ",year," games=",qa$unique_games," game rows=",qa$player_game_rows,
          " player seasons=",qa$season_rows," gz bytes=",qa$game_log_size_bytes)
 rm(b,logs,season_summary);gc(verbose=FALSE)
}
# Select a modest, reproducible, year-spanning research sample per season.
# NEVER trust or consume hoopR's potential lineup, RAPM, or plus/minus features.
# Pull chronological play event fields, including substitutions when ESPN provides them.
pbp_qa<-list()
for(year in if(run_mode %in% c("all","pbp")) years else integer()){
 logpath<-file.path(archive_dir("game_logs"),paste0("player_game_logs_",year,".csv.gz"))
 if(!file.exists(logpath)) stop("PBP needs prior player-game archive: ",logpath)
 logs<-suppressMessages(readr::read_csv(logpath,show_col_types=FALSE,guess_max=5000,
                            col_types=cols(.default=col_character())))
 eligible_games<-logs%>%
   filter(!is.na(team_id),team_id!="",!is.na(game_id),game_id!="")%>%
   group_by(game_id)%>%
   summarise(n_teams=n_distinct(team_id),
             date=first(game_date),
             n_players=n_distinct(athlete_id),.groups="drop")%>%
   filter(n_teams==2,n_players>=10)%>%
   arrange(date,game_id)
 quota<-if(year>=2025)40L else if(year>=2023)24L else 16L
 if(pilot)quota<-3L
 if(nrow(eligible_games)<quota) stop("Insufficient D1 vs D1 box games: ",year)
 # Spread sample across season, avoiding a misleading conference-only run.
 positions<-unique(as.integer(round(seq(1,nrow(eligible_games),length.out=quota))))
 selected<-eligible_games$game_id[positions]
 event_fields<-c("game_id","season","season_type","game_date","period_number","sequence_number",
   "id","play_id","text","type_id","type_text","clock_display_value",
   "home_score","away_score","score_value","scoring_play","shooting_play",
   "team_id","athlete_id_1","athlete_id_2",
   "home_team_id","away_team_id","coordinate_x_raw","coordinate_y_raw")
 collected<-vector("list",length(selected));failed<-character()
 for (i in seq_along(selected)) {
   game<-selected[i]
   p<-NULL
   for(retry in seq_len(3)) {
     p<-tryCatch(hoopR::espn_mbb_pbp(game_id=game),
              error=function(e){log_line("PBP retry ",year," ",game,": ",conditionMessage(e));NULL})
     if(is.data.frame(p)&&nrow(p)>0)break
     Sys.sleep(0.5*retry)
   }
   if(!is.data.frame(p)||nrow(p)<20) {failed<-c(failed,game);next}
   for(f in event_fields) p<-ensure(p,f)
   p<-p%>%select(all_of(event_fields))%>%
     mutate(game_id=as.character(game),season=as.integer(year),
       across(any_of(c("team_id","home_team_id","away_team_id","athlete_id_1","athlete_id_2")),as.character))
   if(all(is.na(p$period_number)) || all(is.na(p$text))) {failed<-c(failed,game);next}
   collected[[i]]<-p
   if(i%%10==0)log_line("PBP ",year,": ",i,"/",length(selected)," games")
   Sys.sleep(0.10)
 }
 out<-bind_rows(collected)
 success<-n_distinct(out$game_id)
 file_pbp<-file.path(archive_dir("selected_pbp"),paste0("raw_espn_pbp_sample_",year,".csv.gz"))
 if(success>0)save_gz_csv(out,file_pbp)
 qa<-list(season=year,source="hoopR::espn_mbb_pbp(game_id) collecting ESPN event fields",
          intended_games=length(selected),successful_games=success,failed_games=as.list(failed),
          event_rows=nrow(out),pbp_file_bytes=if(file.exists(file_pbp))file.info(file_pbp)$size else 0L,
          sampled_game_ids=as.list(as.character(selected)),
          sample_scope="stratified-in-time deterministic D1-vs-D1 sample only; NOT league-wide PBP",
          verified_five_man_lineup_games=0L,trained_rapm=FALSE)
 save_json(qa,file.path("research_qa/historical",paste0("pbp_qa_",year,".json")))
 pbp_qa[[as.character(year)]]<-qa
 log_line("ARCHIVED SELECTED PBP ",year," sample games=",success,"/",length(selected),
         " events=",nrow(out))
 if(success < floor(length(selected)*0.5))stop("Too few PBP samples for ",year,": ",success)
 rm(logs,out);gc(verbose=FALSE)
}
save_json(list(backfill_mode=run_mode,pilot=pilot,years=as.list(years),
  manifest_date_utc=format(Sys.time(),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
  box=box_qa,pbp=pbp_qa,
  production_modified=FALSE,
  interpretation=c("All box scores and game logs backed by hoopR ESPN player box archive.",
   "PBP selected games are event-level facts, NOT official on-court lineups.",
   "No reconstructed RAPM is produced, no third-party derived lineups trusted.",
   "Raw selected PBP excluded from Portal data feed.","All work confined to research branch.")),
 file.path("research_qa/historical",if(pilot)"pilot_manifest.json" else "full_manifest.json"))
log_line("Completed historical ",run_mode," backfill",if(pilot)" (pilot)" else "")
