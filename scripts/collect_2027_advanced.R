# ESPN-native 2026-27 PBP ingestion. Called after the validated 2027 box refresh.
# Never overwrites a previously validated game or changes historical seasons.
if (!exists('active_player_box') || !exists('active_season') || as.integer(active_season) != 2027L) {
  message('Advanced collection skipped: 2027 has no verified player-box feed')
} else {
  suppressPackageStartupMessages(library(dplyr))
  suppressPackageStartupMessages(library(jsonlite))
  raw <- as.data.frame(active_player_box)
  needed <- c('game_id','game_date','team_id','athlete_id','minutes','starter','field_goals_attempted','home_away')
  if (!all(needed %in% names(raw))) stop('Advanced box schema missing: ',paste(setdiff(needed,names(raw)),collapse=','))
  d1 <- as.character(get_d1_teams(2027L)$espn_team_id)
  current <- raw %>% mutate(game_id=as.character(game_id),team_id=as.character(team_id),
      athlete_id=as.character(athlete_id),
      minutes=suppressWarnings(as.numeric(minutes)),
      started=as.logical(starter),fga=suppressWarnings(as.numeric(field_goals_attempted))) %>%
    filter(team_id %in% d1,grepl('^[0-9]+$',game_id),grepl('^[0-9]+$',athlete_id),
      !is.na(game_date),as.Date(game_date)<Sys.Date(),!is.na(minutes),minutes>=0)
  games <- split(current, current$game_id)
  games <- games[vapply(games,function(g) length(unique(g$team_id))==2 &&
      all(vapply(split(g,g$team_id),nrow,integer(1))>=5),logical(1))]
  message('Advanced publisher: ',length(games),' games with two D-I box teams')
  if(length(games)){
    dir.create('data/advanced_2027_pbp/games',recursive=TRUE,showWarnings=FALSE)
    dir.create('data',recursive=TRUE,showWarnings=FALSE)
    # A complete per-player/per-game box reference is mandatory for releasing
    # coordinates or lineup analytics. These are native ESPN, not Torvik data.
    statcol<-function(g,name,default=NA_real_){
      if(name%in%names(g))suppressWarnings(as.numeric(g[[name]])) else rep(default,nrow(g))
    }
    strcol<-function(g,name,default=''){
      if(name%in%names(g))as.character(g[[name]]) else rep(default,nrow(g))
    }
    pieces <- lapply(games,function(g) data.frame(game_id=g$game_id, team_id=g$team_id,
      athlete_id=g$athlete_id, started=as.integer(!is.na(g$started)&g$started),
      minutes=g$minutes, fga=ifelse(is.na(g$fga),0,g$fga),
      fgm=statcol(g,'field_goals_made'),three_pa=statcol(g,'three_point_field_goals_attempted'),
      three_pm=statcol(g,'three_point_field_goals_made'),
      team_score=statcol(g,'team_score'),
      ast=statcol(g,'assists'),reb=statcol(g,'rebounds'),
      position=if('athlete_position_abbreviation'%in%names(g))as.character(g$athlete_position_abbreviation) else '',
      stringsAsFactors=FALSE))
    box <- do.call(rbind,pieces)
    dest <- 'data/advanced_2027_player_box.csv.gz'
    temp <- paste0(dest,'.tmp');con <- gzfile(temp,'wt');write.csv(box,con,row.names=FALSE,na='');close(con)
    if(!file.rename(temp,dest)) stop('Cannot finalize box snapshot')
    fresh <- 0L;fail <- 0L;skipped <- 0L
    for (gid in names(games)) {
      if(fresh>=200L)break # bound network load; backlog processed on later scheduled runs
      file <- file.path('data/advanced_2027_pbp/games',paste0(gid,'.csv.gz'))
      if(file.exists(file) && file.info(file)$size>250L){skipped <- skipped+1L;next}
      p <- tryCatch(hoopR::espn_mbb_pbp(game_id=as.numeric(gid)),error=function(e)NULL)
      if(is.null(p)||!is.data.frame(p)||nrow(p)<50L){fail <- fail+1L;next}
      teams <- games[[gid]]
      home <- unique(teams$team_id[tolower(as.character(teams$home_away))=='home'])
      away <- unique(teams$team_id[tolower(as.character(teams$home_away))=='away'])
      if(length(home)!=1L||length(away)!=1L||home==away){fail <- fail+1L;next}
      getfield <- function(nms, fallback=NA_character_) {
        found <- nms[nms %in% names(p)]
        if(length(found))p[[found[[1]]]] else rep(fallback,nrow(p))
      }
      pick <- data.frame(game_id=rep(gid,nrow(p)),
        sequence_number=getfield(c('sequence_number','game_play_number','id')),
        period_number=getfield(c('period_number','period')),
        clock_display_value=getfield(c('clock_display_value','time')),
        type_text=getfield(c('type_text')),
        text=getfield(c('text')),
        team_id=getfield(c('team_id')),
        athlete_id_1=getfield(c('athlete_id_1','participants_0_athlete_id')),
        athlete_id_2=getfield(c('athlete_id_2','participants_1_athlete_id')),
        scoring_play=getfield(c('scoring_play')),
        score_value=getfield(c('score_value')),
        home_team_id=rep(home,nrow(p)),away_team_id=rep(away,nrow(p)),
        coordinate_x=getfield(c('coordinate_x')),
        coordinate_y=getfield(c('coordinate_y')),stringsAsFactors=FALSE)
      if(any(is.na(pick$period_number)) || all(is.na(pick$type_text)) ||
          all(is.na(pick$clock_display_value)) ||
          length(unique(pick$period_number))<2L){fail <- fail+1L;next}
      temp <- paste0(file,'.tmp');con <- gzfile(temp,'wt');write.csv(pick,con,row.names=FALSE,na='');close(con)
      if(!file.rename(temp,file)){unlink(temp);fail <- fail+1L;next}
      fresh <- fresh+1L
    }
    message('Advanced PBP status: new=',fresh,' cached=',skipped,' deferred/missing=',fail)
  }
}
