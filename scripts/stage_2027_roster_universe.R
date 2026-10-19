#!/usr/bin/env Rscript
# D-I 2026-27 season roster staging / identity lookup.
# Uses ESPN via hoopR. NO production feed, staff sheets or website changes.
# Merges metadata by ESPN athlete ID ONLY. Never assign eligibility from roster/class.
suppressPackageStartupMessages({
 library(hoopR);library(dplyr);library(readr);library(tibble)
 library(purrr);library(jsonlite)
})
season<-2027L;prior_season<-2026L
outdir<-"research_data/staged"
qadir<-"research_qa/roster_integration"
dir.create(outdir,recursive=TRUE,showWarnings=FALSE)
dir.create(qadir,recursive=TRUE,showWarnings=FALSE)
history_path<-file.path(outdir,"player_seasons_2020_2026.csv.gz")
if(!file.exists(history_path))stop("Run stage_historical_history.R first")
hist<-read_csv(history_path,show_col_types=FALSE,
               col_types=cols(.default=col_character()))
stopifnot(nrow(hist)==35209)
history_ids<-unique(hist$athlete_id)
history_lookup<-hist%>%
 mutate(y=as.integer(season))%>%arrange(athlete_id,desc(y))%>%
 distinct(athlete_id,.keep_all=TRUE)%>%
 select(athlete_id,history_name=player_name,
        last_season_with_stats=season,previous_stat_team=team_name)
teams<-hoopR::espn_mbb_teams(year=season)%>%
 mutate(team_id=as.character(team_id))%>%
 transmute(team_id,team_name=as.character(display_name))%>%
 distinct(team_id,.keep_all=TRUE)%>%arrange(team_name)
if(nrow(teams)<350||nrow(teams)>390)stop("Implausible national D1 universe size")
retry<-function(f,max_attempts=3L){
 last<-NULL
 for(i in seq_len(max_attempts)){
  x<-tryCatch(f(),error=function(e){last<<-conditionMessage(e);NULL})
  if(!is.null(x))return(list(value=x,error=""))
  Sys.sleep(0.6*i)
 }
 list(value=NULL,error=if(is.null(last))"no response" else last)
}
normal_ids<-function(d){
 if(is.null(d)||!"athlete_id"%in%names(d))return(character())
 ids<-unique(as.character(d$athlete_id))
 ids[!is.na(ids)&ids!=""&ids!="NA"]
}
clean_char<-function(d,col,n){
 if(col%in%names(d))return(as.character(d[[col]]))
 rep(NA_character_,n)
}
player_rows<-list();team_rows<-list()
for(i in seq_len(nrow(teams))){
 id<-teams$team_id[i];name<-teams$team_name[i]
 cur<-retry(function()hoopR::espn_mbb_team_season_roster(team_id=id,season=season))
 prev<-retry(function()hoopR::espn_mbb_team_season_roster(team_id=id,season=prior_season))
 bio<-retry(function()hoopR::espn_mbb_team_roster(team_id=id,season=season))
 cur_ids<-normal_ids(cur$value);old_ids<-normal_ids(prev$value)
 b<-bio$value
 bio_ok<-!is.null(b)&&"athlete_id"%in%names(b)
 if(bio_ok) {
  b<-as_tibble(b)%>%mutate(athlete_id=as.character(athlete_id))%>%
    filter(!is.na(athlete_id),athlete_id!="")%>%
    distinct(athlete_id,.keep_all=TRUE)
  # Strict season check: site-v2 roster may silently ignore season parameter.
  if("season"%in%names(b)) {
   bs<-unique(as.character(b$season))
   bs<-bs[!is.na(bs)&bs!=""]
   if(length(bs)>0 && !all(bs %in% c("2027")))bio_ok<-FALSE
  }
 }
 if(!bio_ok)b<-tibble(athlete_id=character())
 ncur<-length(cur_ids)
 matches<-sum(cur_ids %in% b$athlete_id)
 new_count<-length(setdiff(cur_ids,old_ids))
 prev_count<-length(old_ids)
 strict_status<-case_when(
  is.null(cur$value) ~ "FETCH_ERROR",
  is.null(prev$value) ~ "PREVIOUS_ROSTER_UNAVAILABLE",
  ncur==0 ~ "EMPTY_CURRENT_ROSTER",
  ncur<10 ~ "SHORT_ROSTER",
  new_count==0 ~ "NO_NEW_IDS_REVIEW",
  !bio_ok || matches/max(1,ncur)<0.95 ~ "INCOMPLETE_BIOS_REVIEW",
  TRUE ~ "UPDATED_NEEDS_FINAL_COMPLETENESS_QA"
 )
 team_rows[[i]]<-tibble(
  team_id=id,team_name=name,roster_season=season,
  prior_roster_ids=prev_count,current_roster_ids=ncur,
  new_ids_not_at_this_team=new_count,
  current_bios_matched=matches,
  bio_coverage=matches/max(1,ncur),
  current_fetch_status=if(is.null(cur$value))cur$error else "OK",
  previous_fetch_status=if(is.null(prev$value))prev$error else "OK",
  bio_fetch_status=if(!bio_ok)paste0("CHECK: ",bio$error) else "OK",
  readiness_status=strict_status
 )
 if(ncur>0) {
  members<-tibble(athlete_id=cur_ids)%>%
   left_join(b,by="athlete_id",relationship="one-to-one")
  player_rows[[i]]<-tibble(
   roster_season=season,athlete_id=members$athlete_id,
   team_id=id,team_name=name,
   espn_name=clean_char(members,"full_name",ncur),
   position=clean_char(members,"position_abbrev",ncur),
   jersey=clean_char(members,"jersey",ncur),
   height=clean_char(members,"height",ncur),
   weight=clean_char(members,"weight",ncur),
   headshot=clean_char(members,"headshot",ncur),
   birth_place=clean_char(members,"birth_place",ncur),
   biography_verified=members$athlete_id %in% b$athlete_id,
   team_readiness_status=strict_status
  )
 }
 if(i%%25==0||i==1||i==nrow(teams))cat("ROSTERS: ",i,"/",nrow(teams),
       " ",name," 2027=",ncur," new=",new_count," status=",strict_status,"\n")
 Sys.sleep(0.08)
}
team_qa<-bind_rows(team_rows)
members<-bind_rows(player_rows)
bad_id<-members%>%count(athlete_id,name="n")%>%filter(n>1)
if(nrow(bad_id)){
  print(bad_id)
  stop("ESPN 2027 athlete IDs assigned to more than one team; quarantine required")
}
members<-members %>%left_join(history_lookup,by="athlete_id",relationship="many-to-one")%>%
 mutate(has_historical_box_stats=!is.na(last_season_with_stats),
        name=coalesce(na_if(espn_name,""),na_if(history_name,"")),
        identity_status=case_when(
          is.na(name) | name=="" ~ "NAME_MISSING_REVIEW",
          !biography_verified ~ "HISTORY_OR_BIO_REVIEW",
          TRUE ~ "ESPN_ID_WITH_BIO"
        ),
        eligible_years_override_status="NOT_IN_PUBLIC_FEED_STAFF_OWNS",
        roster_source="ESPN_season_roster_core_v2_and_site_v2_bio"
 )%>%
 select(roster_season,athlete_id,name,team_id,team_name,
        position,jersey,height,weight,headshot,birth_place,
        has_historical_box_stats,last_season_with_stats,
        previous_stat_team,identity_status,team_readiness_status,
        eligible_years_override_status,roster_source)
# Intentionally NO 'eligibility' value, 'class year', NIL, BPR, or staff notes.
stopifnot(nrow(team_qa)==365,nrow(members)>4000,
          !anyDuplicated(members$athlete_id))
write_csv(team_qa,file.path(qadir,"all_team_2027_readiness.csv"))
write_csv(members,file.path(outdir,"current_roster_2027_identity.csv"))
# A SMALL, independent roster file. It is not imported by any live Portal today.
roster_json<-list(
 schemaVersion=1L,rosterSeason=season,source="ESPN factual roster metadata via hoopR",
 generatedAt=format(Sys.time(),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
 totalTeams=nrow(teams),totalRosterPlayers=nrow(members),
 warning="Research staging ONLY; team freshness varies, eligibility is staff-maintained; no auto-merge by player name.",
 players=lapply(seq_len(nrow(members)),function(i) {
  r<-members[i,]
  list(espnAthleteId=r$athlete_id[[1]],name=r$name[[1]],
       teamId=r$team_id[[1]],team=r$team_name[[1]],
       position=r$position[[1]],jersey=r$jersey[[1]],
       height=r$height[[1]],weight=r$weight[[1]],
       headshot=r$headshot[[1]],
       birthPlace=r$birth_place[[1]],
       rosterSeason=season,
       historicalBoxStats=r$has_historical_box_stats[[1]],
       identityStatus=r$identity_status[[1]],
       teamReadiness=r$team_readiness_status[[1]])
 })
)
jsonlite::write_json(roster_json,file.path(outdir,"current_roster_2027_candidate.json"),
 auto_unbox=TRUE,na="null",null="null")
sum_qa<-list(
 season=season,total_d1_teams=nrow(teams),current_roster_ids=nrow(members),
 unique_athlete_ids=n_distinct(members$athlete_id),
 new_to_2019_2026_box_archive=sum(!members$has_historical_box_stats),
 existing_history_matches=sum(members$has_historical_box_stats),
 missing_name=sum(is.na(members$name)|members$name==""),
 missing_espn_bio=sum(members$identity_status!="ESPN_ID_WITH_BIO"),
 no_new_id_teams=sum(team_qa$readiness_status=="NO_NEW_IDS_REVIEW"),
 updated_candidate_teams=sum(team_qa$readiness_status=="UPDATED_NEEDS_FINAL_COMPLETENESS_QA"),
 short_roster_teams=sum(team_qa$readiness_status=="SHORT_ROSTER"),
 fetch_issue_teams=sum(grepl("FETCH|UNAVAILABLE",team_qa$readiness_status)),
 min_roster_n=min(team_qa$current_roster_ids),
 max_roster_n=max(team_qa$current_roster_ids),
 roster_candidate_json_bytes=file.info(file.path(outdir,"current_roster_2027_candidate.json"))$size,
 import_ready=FALSE,
 staff_eligibility_protected=TRUE,
 no_fabricated_game_stats=TRUE,
 no_fabricated_eligibility=TRUE,
 not_published_to_main=TRUE)
jsonlite::write_json(sum_qa,file.path(qadir,"roster_2027_stage_qa.json"),
 auto_unbox=TRUE,pretty=TRUE)
print(sum_qa)
if(sum_qa$fetch_issue_teams>3)stop("Too many failed team fetches")
if(sum_qa$missing_name>50)stop("Too many unnamed player records")
