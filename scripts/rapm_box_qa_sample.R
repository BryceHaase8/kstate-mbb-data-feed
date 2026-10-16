# Isolated RAPM development QA: ESPN official box minutes for 25 selected games.
# This script is NOT part of the daily Portal factual-data workflow.
suppressPackageStartupMessages({
 library(hoopR)
 library(dplyr)
 library(readr)
 library(tibble)
})
ids <- c("401804832","401804898","401804942","401805168","401805206",
"401806377","401806453","401806503","401807689","401807724",
"401807762","401808173","401808211","401808251","401808464",
"401808497","401808535","401808607","401808638","401808676",
"401808710","401808896","401808933","401808976","401809103")
b <- as_tibble(hoopR::load_mbb_player_box(seasons=2026))
required <- c("game_id","athlete_id","team_id","minutes")
missing <- setdiff(required,names(b))
if(length(missing))stop(paste("Missing player-box columns",paste(missing,collapse=", ")))
for(nm in c("starter","athlete_display_name","team_display_name","did_not_play")){
 if(!nm %in% names(b))b[[nm]] <- NA
}
out <- b %>% mutate(game_id=as.character(game_id),athlete_id=as.character(athlete_id),
                     team_id=as.character(team_id)) %>%
 filter(game_id %in% ids) %>%
 transmute(game_id,athlete_id,team_id,player_name=athlete_display_name,
   team_name=team_display_name,starter,did_not_play,minutes=as.character(minutes)) %>%
 arrange(game_id,team_id,athlete_id)
if(n_distinct(out$game_id)<20)stop(paste("Only",n_distinct(out$game_id),"sample games found"))
dir.create("research_qa",showWarnings=FALSE)
write_csv(out,"research_qa/espn_player_box_25_games.csv")
cat("Wrote official ESPN box for",n_distinct(out$game_id),"games,",nrow(out),"player rows\n")
