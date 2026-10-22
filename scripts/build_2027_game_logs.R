# 2026-27 game logs. Same hoopR player box already fetched by daily_update.R.
# Writes independently versioned 25-field ESPN ID shards, never historical years.
stopifnot(exists("active_player_box"),exists("active_season"))
if(as.integer(active_season)==2027L){
 suppressPackageStartupMessages(library(dplyr))
 suppressPackageStartupMessages(library(jsonlite))
 raw<-as_tibble(active_player_box)
 req<-c("athlete_id","game_id","game_date","team_id","team_display_name",
        "opponent_team_display_name","home_away","team_score",
        "opponent_team_score","minutes","points","rebounds","assists",
        "steals","blocks","turnovers","fouls","field_goals_made",
        "field_goals_attempted","three_point_field_goals_made",
        "three_point_field_goals_attempted","free_throws_made",
        "free_throws_attempted","offensive_rebounds","defensive_rebounds","starter")
 missing<-setdiff(req,names(raw))
 if(length(missing))stop("ESPN 2027 box-score schema missing: ",paste(missing,collapse=","))
 if(!"did_not_play"%in%names(raw))raw$did_not_play<-NA
 d1<-get_d1_teams(2027L)$espn_team_id
 x<-raw%>%mutate(athlete_id=as.character(athlete_id),
   team_id=as.character(team_id),game_id=as.character(game_id),
   played=case_when(!is.na(did_not_play)&as.logical(did_not_play)~FALSE,
      coalesce(as.numeric(minutes),0)>0~TRUE,
      coalesce(as.logical(starter),FALSE)~TRUE,
      coalesce(as.numeric(points),0)>0~TRUE,
      coalesce(as.numeric(rebounds),0)>0~TRUE,
      coalesce(as.numeric(assists),0)>0~TRUE,
      coalesce(as.numeric(steals),0)>0~TRUE,
      coalesce(as.numeric(blocks),0)>0~TRUE,TRUE~FALSE))%>%
    filter(team_id%in%d1,grepl("^[0-9]+$",athlete_id),
           grepl("^[0-9]+$",game_id),played)%>%
    distinct(athlete_id,game_id,.keep_all=TRUE)
 if(nrow(x)<20)stop("Too few verified 2027 player games")
 if(any(is.na(x$game_date))||
    any(is.na(x$opponent_team_display_name)|x$opponent_team_display_name==""))
     stop("2027 schedule metadata missing")
 n<-function(r,k){v<-suppressWarnings(as.numeric(r[[k]]));if(is.na(v))0 else v}
 t<-function(r,k){v<-as.character(r[[k]]);if(!length(v)||is.na(v))"" else v}
 row<-function(i){r<-x[i,];list(2027L,t(r,"game_id"),t(r,"game_date"),
    t(r,"team_display_name"),t(r,"opponent_team_display_name"),
    t(r,"home_away"),n(r,"team_score"),n(r,"opponent_team_score"),
    as.integer(n(r,"starter")),n(r,"minutes"),n(r,"points"),
    n(r,"rebounds"),n(r,"assists"),n(r,"steals"),n(r,"blocks"),
    n(r,"turnovers"),n(r,"fouls"),n(r,"field_goals_made"),
    n(r,"field_goals_attempted"),n(r,"three_point_field_goals_made"),
    n(r,"three_point_field_goals_attempted"),n(r,"free_throws_made"),
    n(r,"free_throws_attempted"),n(r,"offensive_rebounds"),
    n(r,"defensive_rebounds"))}
 fields<-c("season","gameId","date","team","opponent","homeAway",
    "teamScore","opponentScore","started","minutes","pts","reb",
    "ast","stl","blk","tov","pf","fgm","fga","threePm",
    "threePa","ftm","fta","oreb","dreb")
 records<-lapply(seq_len(nrow(x)),row)
 if(!all(vapply(records,length,integer(1))==25))stop("Wrong game-log row width")
 path<-"public/portal_game_logs_2027"
 dir.create(path,recursive=TRUE,showWarnings=FALSE)
 shards<-as.integer(x$athlete_id)%%128L
 for(s in 0:127){
    index<-which(shards==s);byid<-list()
    if(length(index)){
      grouped<-split(index,x$athlete_id[index])
      byid<-lapply(grouped,function(ids)unname(records[ids]))
    }
    item<-list(schemaVersion=1L,modulo=128L,shard=as.integer(s),
               season=2027L,fields=fields,players=byid)
    jsonlite::write_json(item,file.path(path,sprintf("games_%03d.json",s)),
           auto_unbox=TRUE,na="null",null="null",digits=NA)
 }
 message("ESPN 2027 game log shards staged for ",length(unique(x$athlete_id))," athletes")
}
