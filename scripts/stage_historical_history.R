#!/usr/bin/env Rscript
# Stage existing authoritative 2023–26 + previously audited 2020–22 historical totals.
# RESEARCH BRANCH ONLY: NEVER overwrite main data/current_player_season_stats.csv
# or public/portal_factual_data.json, nor import roster-only players as fake 0-GP seasons.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(jsonlite)
})
archive_root <- "research_data/historical/season_totals"
production <- "data/current_player_season_stats.csv"
out_dir <- "research_data/staged"
qa_dir <- "research_qa/roster_integration"
dir.create(out_dir, recursive=TRUE, showWarnings=FALSE)
dir.create(qa_dir, recursive=TRUE, showWarnings=FALSE)
stopifnot(file.exists(production))
source_prod <- readr::read_csv(production, show_col_types=FALSE,
                              col_types=cols(.default=col_character()))
stopifnot(setequal(sort(unique(as.integer(source_prod$season))),2023:2026),
          nrow(source_prod)==20303,
          !anyDuplicated(paste(source_prod$season,source_prod$athlete_id)))
expected_counts <- c("2020"=4796L,"2021"=5020L,"2022"=5090L)
additions <- lapply(2020:2022,function(year){
  path <- file.path(archive_root,paste0("player_season_",year,".csv.gz"))
  if(!file.exists(path)) stop("Historical file missing: ",path)
  x <- readr::read_csv(path, show_col_types=FALSE,
                       col_types=cols(.default=col_character()))
  if(nrow(x)!=expected_counts[[as.character(year)]])
    stop("Historical ",year,": changed row count ",nrow(x))
  if(!identical(names(x),names(source_prod))) stop("Archive schema differs in ",year)
  if(!all(x$season==as.character(year))) stop("Wrong season in ",path)
  if(anyDuplicated(x$athlete_id)) stop("Duplicate historical athlete ID ",year)
  x
})
joined <- dplyr::bind_rows(c(additions,list(source_prod))) %>%
  mutate(season_num=as.integer(season)) %>%
  arrange(season_num, athlete_id) %>%
  select(-season_num)
if(nrow(joined)!=35209 || anyDuplicated(paste(joined$season,joined$athlete_id)))
 stop("7-season staging total/identities incorrect")
# Compare production years in memory, including entire row text. Never replace data silently.
old <- joined%>%filter(as.integer(season)>=2023)%>%
  arrange(as.integer(season), athlete_id)
ref <- source_prod %>% arrange(as.integer(season),athlete_id)
if(!identical(as.data.frame(old),as.data.frame(ref)))
  stop("Overlap years 2023–26 changed during staging")
dest <- file.path(out_dir,"player_seasons_2020_2026.csv.gz")
w <- gzfile(dest,"wb");utils::write.csv(joined,w,row.names=FALSE,na="");close(w)
qa <- list(
  result="PASS",staging_only=TRUE,
  archived_seasons=as.list(2020:2026),player_seasons=nrow(joined),
  preexisting_player_seasons=nrow(source_prod),
  added_player_seasons=sum(vapply(additions,nrow,integer(1))),
  existing_2023_2026_identical=TRUE,
  unique_espn_athlete_ids=length(unique(joined$athlete_id)),
  roster_only_players_not_fabricated=TRUE,
  data_size_bytes=unname(file.info(dest)$size),
  public_homepage_json_unchanged=TRUE,
  # 7 seasons means current all-in-one public feed increases to >30MB.
  # Serve roster separately and stage a split/lazy historical API before promotion.
  recommendation="Do not publish expanded public JSON until frontend performance is tested."
)
jsonlite::write_json(qa,file.path(qa_dir,"history_migration_qa.json"),
  auto_unbox=TRUE,pretty=TRUE)
print(qa)
