#!/usr/bin/env Rscript
# Verify the full canonical 2020–26 CSV and rebuild the legacy public feed
# with 2023–26 only. Research branch until staff approves promotion.
suppressPackageStartupMessages({
 library(readr);library(dplyr);library(jsonlite)
})
src <- "research_data/staged/player_seasons_2020_2026.csv.gz"
dest <- "data/current_player_season_stats.csv"
qa_dir <- "research_qa/roster_integration"
if(!file.exists(src))stop("Missing staged seven-year archive")
historical <-readr::read_csv(src,show_col_types=FALSE,
                             col_types=cols(.default=col_character()))
baseline <-readr::read_csv(dest,show_col_types=FALSE,
                           col_types=cols(.default=col_character()))
stopifnot(nrow(historical)==35209,nrow(baseline)==20303,
          !anyDuplicated(paste(historical$season,historical$athlete_id)),
          identical(names(historical),names(baseline)))
existing<-historical%>%
 filter(as.integer(season)>=2023) %>%
 arrange(as.integer(season),athlete_id)
current<-baseline%>%
 arrange(as.integer(season),athlete_id)
if(!identical(as.data.frame(existing),as.data.frame(current)))
 stop("Historical staging would mutate preexisting 2023–26 statistics")
# Note: NO Netlify/Portal action runs on this branch.
readr::write_csv(historical,dest)
source("scripts/build_public_factual_json.R")
json <-jsonlite::fromJSON("public/portal_factual_data.json",simplifyVector=FALSE)
yrs<-as.integer(unlist(json$seasons))
if(!identical(yrs,2023:2026))stop("Public JSON changed the original 4 seasons")
if(json$playerSeasonCount!=20303 || json$playerCount!=10476)
 stop("Public feed cardinality changed — refusing to promote")
if(json$latestSeason!=2026 || length(json$players)!=10476)
 stop("Public feed player identities changed")
qa<-list(status="PASS",
 canonical_archive_seasons=as.list(2020:2026),
 canonical_archive_player_seasons=nrow(historical),
 added_to_canonical_archive=nrow(historical)-nrow(baseline),
 unchanged_old_player_rows=nrow(baseline),
 public_feed_seasons=as.list(yrs),
 public_feed_player_seasons=json$playerSeasonCount,
 public_feed_unique_players=json$playerCount,
 public_feed_schema_version=json$schemaVersion,
 public_feed_unchanged_in_scope=TRUE,
 no_2027_roster_in_main=TRUE,
 promotion_pending_staff_review=TRUE)
dir.create(qa_dir,recursive=TRUE,showWarnings=FALSE)
jsonlite::write_json(qa,file.path(qa_dir,"seven_year_prod_candidate_qa.json"),
                     pretty=TRUE,auto_unbox=TRUE)
print(qa)
