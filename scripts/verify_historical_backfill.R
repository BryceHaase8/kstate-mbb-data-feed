#!/usr/bin/env Rscript
# Independent QA of one-time research archives vs existing main data snapshot.
# Does not modify production or ingest PBP into RAPM.
suppressPackageStartupMessages({
 library(dplyr);library(readr);library(jsonlite);library(tibble)
})
num<-function(x)suppressWarnings(as.numeric(x))
root<-"research_data/historical"
existing<-read_csv("data/current_player_season_stats.csv",show_col_types=FALSE,
                   col_types=cols(.default=col_character()))
root_qa<-"research_qa/historical"
dir.create(root_qa,recursive=TRUE,showWarnings=FALSE)
reports<-list();fatal<-character()
for(y in 2020:2026){
 sf<-file.path(root,"season_totals",paste0("player_season_",y,".csv.gz"))
 gf<-file.path(root,"game_logs",paste0("player_game_logs_",y,".csv.gz"))
 pf<-file.path(root,"selected_pbp",paste0("raw_espn_pbp_sample_",y,".csv.gz"))
 if(!file.exists(sf)||!file.exists(gf)){
   fatal<-c(fatal,paste(y,"missing season or game archive"));next
 }
 seas<-read_csv(sf,show_col_types=FALSE,col_types=cols(.default=col_character()))
 logs<-read_csv(gf,show_col_types=FALSE,col_types=cols(.default=col_character()))
 if(nrow(seas)<3500 || nrow(logs)<30000)
   fatal<-c(fatal,paste(y,"too few archived records"))
 dups<-nrow(logs)-nrow(distinct(logs,game_id,team_id,athlete_id))
 if(dups)fatal<-c(fatal,paste(y,"duplicate game player keys:",dups))
 sdups<-nrow(seas)-nrow(distinct(seas,season,athlete_id))
 if(sdups)fatal<-c(fatal,paste(y,"duplicate player season keys:",sdups))
 # Independent reaggregation of each selected athlete's season-team line.
 # The current production aggregator keeps one team if a player has two.
 perteam<-logs%>%
  group_by(athlete_id,team_id)%>%
  summarise(games=n_distinct(game_id),sum_points=sum(num(points),na.rm=TRUE),
            sum_minutes=sum(num(minutes),na.rm=TRUE),
            sum_fga=sum(num(fga),na.rm=TRUE),.groups="drop")
 combined<-seas%>%left_join(perteam,by=c("athlete_id","team_id"))
 mismatch<-combined%>%filter(is.na(games)|
        num(gp)!=games|
        abs(num(pts)-sum_points)>0.0001 |
        abs(num(minutes)-sum_minutes)>0.0001 |
        abs(num(fga)-sum_fga)>0.0001)
 if(nrow(mismatch)>nrow(seas)*0.001)fatal<-c(fatal,paste(y,"season stats vs game rows discrepancy",nrow(mismatch)))
 # Observe, do NOT silently overwrite current live historical totals.
 prior<-existing%>%filter(as.integer(season)==y)
 overlap<-NULL
 if(nrow(prior)){
   j<-seas%>%select(athlete_id,all_of(c("pts","gp","minutes","fgm","fga","ast","reb","three_pm","three_pa")))%>%
      inner_join(prior%>%select(athlete_id,all_of(c("pts","gp","minutes","fgm","fga","ast","reb","three_pm","three_pa"))),
                 by="athlete_id",suffix=c("_archive","_main"))
   changed<-rep(FALSE,nrow(j))
   for(n in c("pts","gp","minutes","fgm","fga","ast","reb","three_pm","three_pa")){
     changed<-changed | coalesce(abs(num(j[[paste0(n,"_archive")]])-
                    num(j[[paste0(n,"_main")]]))>0.00001,TRUE)
   }
   overlap<-list(main_player_seasons=nrow(prior),matched_athlete_ids=nrow(j),
     archived_player_seasons=nrow(seas),stat_changed_on_matched=sum(changed),
     changed_share_if_matched=if(nrow(j))sum(changed)/nrow(j) else NULL,
     dropped_main_athletes=sum(!prior$athlete_id %in% seas$athlete_id),
     newly_archived_athletes=sum(!seas$athlete_id %in% prior$athlete_id))
 }
 pbp<-NULL
 if(file.exists(pf)){
   plays<-read_csv(pf,show_col_types=FALSE,col_types=cols(.default=col_character()))
   pbp<-list(event_rows=nrow(plays),n_games=n_distinct(plays$game_id),
     missing_event_text=sum(is.na(plays$text)|plays$text==""))
 }
 reports[[as.character(y)]]<-list(
  year=y,player_seasons=nrow(seas),
  player_game_rows=nrow(logs),
  games=n_distinct(logs$game_id),
  d1_teams=n_distinct(logs$team_id),
  duplicate_game_player_keys=dups,
  duplicate_season_player_keys=sdups,
  season_totals_disagree_with_archived_logs=nrow(mismatch),
  production_comparison=overlap,pbp_selected_archive=pbp)
 cat("QA ",y,": ",nrow(seas)," players ",nrow(logs)," player-games ",
     nrow(mismatch)," game/season mismatches\n")
 rm(logs,seas);gc(verbose=FALSE)
}
res<-list(validated_at=format(Sys.time(),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
 all_seven_seasons_archived=length(reports)==7 && length(fatal)==0,
 years=reports, fatal_issues=as.list(fatal),
 interpretation="Research-only data QA; differences from main do not overwrite production. PBP event presence is not lineup/RAPM validation.")
write_json(res,file.path(root_qa,"verification_2020_2026.json"),pretty=TRUE,auto_unbox=TRUE,na="null")
if(length(fatal))stop(paste(fatal,collapse="; "))
cat("Seven-season archive completed all game-log, totals, and key checks.\n")
