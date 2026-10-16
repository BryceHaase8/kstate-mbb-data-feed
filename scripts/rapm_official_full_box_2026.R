# Research-only full-year ESPN official player game box file for independent RAPM QA.
suppressPackageStartupMessages({library(hoopR);library(dplyr);library(readr)})
season <- 2026L
b <- hoopR::load_mbb_player_box(seasons=season) %>% as_tibble()
keys <- c("game_id","athlete_id","team_id","starter","minutes","points",
  "field_goals_attempted","offensive_rebounds","turnovers","free_throws_attempted")
miss <- setdiff(keys,names(b))
if(length(miss)) stop(paste("Missing box columns:",paste(miss,collapse=", ")))
out <- b %>% transmute(
 game_id=as.character(game_id), athlete_id=as.character(athlete_id),
 team_id=as.character(team_id), starter=as.logical(starter),
 minutes=as.numeric(minutes),points=as.numeric(points),
 field_goals_attempted=as.numeric(field_goals_attempted),
 offensive_rebounds=as.numeric(offensive_rebounds),
 turnovers=as.numeric(turnovers),
 free_throws_attempted=as.numeric(free_throws_attempted)
) %>% filter(!is.na(game_id),!is.na(team_id),!is.na(athlete_id)) %>%
  arrange(game_id, team_id, athlete_id)
dir.create("research_qa",showWarnings=FALSE)
con <- gzfile("research_qa/espn_player_box_2026.csv.gz","wb")
write.csv(out,con,row.names=FALSE,na="")
close(con)
cat("Games:",n_distinct(out$game_id),"Teams:",n_distinct(out$team_id),"Player rows:",nrow(out),"\n")
