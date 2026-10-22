#!/usr/bin/env Rscript
# Research only: empirical percentiles for 2025-26 D1 vs D1 team-game box scores.
# Same box-possession formulas as the portal Games tab; no staff/site writes.
suppressPackageStartupMessages({library(hoopR);library(dplyr);library(jsonlite)})
box<-as.data.frame(hoopR::load_mbb_team_box(seasons=2026))
needed<-c("game_id","team_id","team_score","field_goals_made","field_goals_attempted",
"three_point_field_goals_made","free_throws_attempted","offensive_rebounds",
"defensive_rebounds","turnovers")
missing<-setdiff(needed,names(box))
if(length(missing))stop("Missing team-box fields: ",paste(missing,collapse=","),
" || Got: ",paste(names(box),collapse=","))
num<-c("team_score","field_goals_made","field_goals_attempted",
 "three_point_field_goals_made","free_throws_attempted",
 "offensive_rebounds","defensive_rebounds","turnovers")
box<-box%>%mutate(across(all_of(num), ~ suppressWarnings(as.numeric(.x))),
                  game_id=as.character(game_id),team_id=as.character(team_id))%>%
 filter(!is.na(game_id),!is.na(team_id),game_id!="",team_id!="")
# Each valid game must have exactly two distinct team rows; historical 2026
# D1 game box archive commonly contains ~5-6k games.
pairs<-box%>%count(game_id)%>%filter(n==2)%>%pull(game_id)
x<-box%>%filter(game_id%in%pairs)%>%group_by(game_id)%>%
 mutate(opponent_dreb=rev(defensive_rebounds))%>%ungroup()%>%
 mutate(possessions=field_goals_attempted-offensive_rebounds+turnovers+0.44*free_throws_attempted,
        ppp=team_score/possessions,
        efg=(field_goals_made+0.5*three_point_field_goals_made)/field_goals_attempted,
        tovPct=turnovers/possessions,
        orebPct=offensive_rebounds/(offensive_rebounds+opponent_dreb),
        ftRate=free_throws_attempted/field_goals_attempted)
x<-x%>%filter(is.finite(possessions),possessions>=35,possessions<=110,
             field_goals_attempted>=30,field_goals_attempted<=120,
             team_score>=30,team_score<=200,field_goals_made<=field_goals_attempted,
             three_point_field_goals_made<=field_goals_made)
fields<-c("ppp","efg","tovPct","orebPct","ftRate")
qs<-list();ns<-list()
for(key in fields){
 v<-x[[key]];v<-v[is.finite(v)]
 v<-v[v>=0]
 if(key%in%c("efg","tovPct","orebPct"))v<-v[v<=1]
 if(key=="ppp")v<-v[v<=2.2]
 if(key=="ftRate")v<-v[v<=1.5]
 if(length(v)<3000)stop("Too few valid D1 game-level ",key,": ",length(v))
 qs[[key]]<-unname(round(as.numeric(quantile(v,probs=seq(0,1,.01),type=7)),5))
 ns[[key]]<-length(v)
}
dir.create("research_qa/games",showWarnings=FALSE,recursive=TRUE)
payload<-list(schemaVersion=1L,
 source="hoopR 2025-26 ESPN Division I team game box scores",
 season=2026L,description="Descriptive D-I team-game performance percentiles. PPP and possessions are box-score estimates. Not adjusted for opponent or game state.",
 games=length(unique(x$game_id)),teamGames=nrow(x),
 metricSampleSizes=ns,
 definitions=list(ppp="PTS/(FGA-OREB+TOV+0.44*FTA)",efg="(FGM+0.5*3PM)/FGA",
 tovPct="TOV/(FGA-OREB+TOV+0.44*FTA)",orebPct="OREB/(OREB+opponent DREB)",
 ftRate="FTA/FGA"),
 percentiles=qs)
jsonlite::write_json(payload,"research_qa/games/2026_game_factor_percentiles.json",auto_unbox=TRUE,pretty=TRUE,digits=NA)
print(payload[c("games","teamGames","metricSampleSizes")])
