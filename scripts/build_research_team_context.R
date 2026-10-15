# ESPN-only opponent-adjusted team ranking and season-specific conference feed.
# Run after factual player stats are rebuilt; completed years are preserved.
# Public data includes no Portal/staff fields. This is NOT a Torvik/KenPom rating.
suppressPackageStartupMessages({library(hoopR);library(dplyr);library(readr);library(jsonlite)})
INPUT <- "data/current_player_season_stats.csv"
OUTPUT <- "public/research_team_context.json"
if(!file.exists(INPUT))stop("Missing current_player_season_stats.csv")
p <- read_csv(INPUT,col_types=cols(.default=col_character()),show_col_types=FALSE)
stopifnot(all(c("season","team_id","team_name") %in% names(p)))
p <- p %>% filter(!is.na(season),!is.na(team_id),team_id!="") %>% mutate(season=as.integer(season)) %>% filter(!is.na(season))
years <- sort(unique(p$season)); active <- max(years)
old <- if(file.exists(OUTPUT))tryCatch(fromJSON(OUTPUT,simplifyVector=FALSE)$teams,error=function(e)list()) else list()
if(is.null(old)||!is.list(old))old<-list()
aliases <- c(B12="Big 12",BIG12="Big 12",B10="Big Ten",BIGTEN="Big Ten",SEC="SEC",ACC="ACC",MVC="MVC",A10="A10",ATLANTIC10="A10",WCC="WCC",MWC="MWC",MOUNTAINWEST="MWC",BE="Big East",BIGEAST="Big East",AAC="American",AMERICAN="American",CAA="CAA",CUSA="CUSA",MAC="MAC",WAC="WAC",SBC="Sun Belt",SUNBELT="Sun Belt",BSKY="Big Sky",BIGSKY="Big Sky",OVC="OVC",ASUN="ASUN",MEAC="MEAC",SWAC="SWAC",MAAC="MAAC",NEC="NEC",SOCON="SoCon",PATRIOT="Patriot",HORIZON="Horizon",BSOUTH="Big South",BIGSOUTH="Big South",SUMMIT="Summit",SOUTHLAND="Southland",BIGWEST="Big West",IVY="Ivy",AEC="America East")
build <- function(yr){
  teams <- p %>% filter(season==yr) %>% group_by(team_id) %>% summarise(name=first(team_name),.groups="drop")
  ids <- teams$team_id
  meta <- as_tibble(espn_mbb_teams(year=yr))
  if(!nrow(meta)||!"team_id"%in%names(meta))stop(paste("Missing team listing",yr))
  if(!"conference_short_name"%in%names(meta))meta$conference_short_name<-NA_character_
  if(!"conference_name"%in%names(meta))meta$conference_name<-NA_character_
  meta <- meta %>% mutate(team_id=as.character(team_id)) %>% distinct(team_id,.keep_all=TRUE)
  schedule <- as_tibble(load_mbb_schedule(seasons=yr))
  req <- c("home_id","away_id","home_score","away_score","status_type_completed")
  if(length(setdiff(req,names(schedule))))stop(paste("Schedule schema incomplete",yr))
  if(!"game_id"%in%names(schedule))schedule$game_id<-seq_len(nrow(schedule))
  if(!"neutral_site"%in%names(schedule))schedule$neutral_site<-FALSE
  if(!"season_type"%in%names(schedule))schedule$season_type<-2L
  g <- schedule %>% mutate(home_id=as.character(home_id),away_id=as.character(away_id),
    hs=suppressWarnings(as.numeric(home_score)),ascore=suppressWarnings(as.numeric(away_score)),
    complete=tolower(as.character(status_type_completed))=="true",
    neutral=coalesce(as.logical(neutral_site),FALSE)) %>%
    filter(complete,season_type %in% c(2,3),!is.na(hs),!is.na(ascore),
      home_id %in% ids,away_id %in% ids,home_id!=away_id) %>% distinct(game_id,.keep_all=TRUE)
  if(yr<active&&nrow(g)<3000)stop(paste("Historical schedule incomplete",yr,nrow(g)))
  counts <- setNames(rep(0L,length(ids)),ids)
  rating <- setNames(rep(0,length(ids)),ids)
  if(nrow(g)){
    ha <- ifelse(g$neutral,0,3)
    rows <- rbind(data.frame(team=g$home_id,opp=g$away_id,margin=g$hs-g$ascore-ha),
      data.frame(team=g$away_id,opp=g$home_id,margin=g$ascore-g$hs+ha))
    counts[] <- as.integer(table(factor(rows$team,levels=ids)))
    for(iter in seq_len(65)){
      tmp <- rowsum(rows$margin+rating[as.character(rows$opp)],rows$team,reorder=FALSE)
      nextRating <- setNames(rep(0,length(ids)),ids)
      common <- intersect(rownames(tmp),ids)
      nextRating[common] <- tmp[common,1]/pmax(1,counts[common])
      nextRating <- nextRating-mean(nextRating[counts>0])
      nextRating <- nextRating*(counts/(counts+5))
      rating <- .4*rating+.6*nextRating
    }
  }
  ranked <- ids[counts>=5]
  ranked <- ranked[order(-rating[ranked],ranked)]
  rank <- setNames(rep(NA_integer_,length(ids)),ids)
  rank[ranked] <- seq_along(ranked)
  out <- list()
  for(i in seq_along(ids)){
    id <- ids[[i]]; row <- meta[meta$team_id==id,,drop=FALSE]
    con <- if(nrow(row)&&!is.na(row$conference_short_name[[1]])&&nzchar(row$conference_short_name[[1]]))as.character(row$conference_short_name[[1]]) else NULL
    if(!is.null(con)){
      key <- toupper(gsub("[^A-Za-z0-9]","",con))
      if(key %in% names(aliases))con <- unname(aliases[[key]])
    }
    out[[id]] <- list(name=teams$name[[i]],conference=con,
      conferenceName=if(nrow(row))as.character(row$conference_name[[1]]) else NULL,
      rank=unname(rank[[id]]),rankTotal=length(ranked),rating=round(unname(rating[[id]]),3),
      games=unname(counts[[id]]))
  }
  if(yr<active && sum(vapply(out,function(x)!is.null(x$conference),logical(1)))<200)stop(paste("Historical conference coverage low",yr))
  cat("ESPN research team context",yr,": teams",length(out),"games",nrow(g),"ranked",length(ranked),"\n")
  out
}
for(yr in years){
  key<-as.character(yr)
  if(yr==active||is.null(old[[key]])||length(old[[key]])<320){
    candidate<-tryCatch(build(yr),error=function(e){message("Team context unavailable ",yr,": ",conditionMessage(e));NULL})
    if(!is.null(candidate))old[[key]]<-candidate
  }
}
if(!length(old))stop("No team-context seasons available; not writing JSON")
payload<-list(schemaVersion=1,generatedAt=format(Sys.time(),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
  latestSeason=active,seasonCount=length(old),
  meta=list(source="ESPN via hoopR schedule and seasonal team listings",
  rating="D-I opponent-adjusted scoring margin; fixed 3-point home adjustment and shrinkage; not KenPom/Torvik",
  minGamesForRank=5,notes="Completed seasons cached; only latest player-stat season refreshed"),
  teams=old)
dir.create(dirname(OUTPUT),recursive=TRUE,showWarnings=FALSE)
write_json(payload,OUTPUT,auto_unbox=TRUE,pretty=FALSE,na="null",null="null",digits=NA)
cat("Wrote",OUTPUT,"season count",length(old),"\n")