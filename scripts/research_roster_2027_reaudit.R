#!/usr/bin/env Rscript
# Research-only national preseason ESPN roster freshness comparison.
# This queries hoopR's *season-specific* ESPN roster IDs in 2026 and 2027.
# No Portal import, model update, or Netlify deployment.
# Baseline: Oct 13, 2026 historical audit: 133 of 365 had >=1 new athlete ID.
suppressPackageStartupMessages({
  library(hoopR);library(dplyr);library(purrr);library(readr)
  library(tibble);library(jsonlite)
})
outdir <- "research_qa/espn_roster_2027"
dir.create(outdir, recursive=TRUE,showWarnings=FALSE)

cat("TEAM_UNIVERSE: querying ESPN 2027 D-I teams\n")
teamraw <- hoopR::espn_mbb_teams(year=2027)
stopifnot("team_id" %in% names(teamraw), "display_name" %in% names(teamraw))
teams <- teamraw %>% transmute(team_id=as.character(team_id),
    team_name=as.character(display_name)) %>%
    filter(!is.na(team_id),team_id!="") %>%
    distinct(team_id,.keep_all=TRUE) %>% arrange(team_name)
if(nrow(teams)<350 || nrow(teams)>390) stop("D-I universe outside expected count: ",nrow(teams))
cat("D-I teams: ",nrow(teams),"\n")

one_team <- function(id, team, year) {
  rows <- NULL
  last_error <- ""
  for (attempt in seq_len(3)) {
    rows <- tryCatch(hoopR::espn_mbb_team_season_roster(team_id=id,season=year),
      error=function(e){last_error <<- conditionMessage(e); NULL})
    if(!is.null(rows))break
    Sys.sleep(0.5*attempt)
  }
  if(is.null(rows)) {
    return(list(ids=character(),status="FETCH_ERROR",error=last_error))
  }
  if(!"athlete_id" %in% names(rows)) {
    return(list(ids=character(),status="SCHEMA_ERROR",error=paste("no athlete_id:",paste(names(rows),collapse=","))))
  }
  ids <- unique(as.character(rows$athlete_id))
  ids <- ids[!is.na(ids) & ids!="" & ids!="NA"]
  list(ids=ids,status=if(length(ids)==0)"EMPTY" else "OK",error="")
}

old <- vector("list",nrow(teams));new <- vector("list",nrow(teams))
for (i in seq_len(nrow(teams))) {
  tid <- teams$team_id[i];nm <- teams$team_name[i]
  if (i %% 25==1 || i==nrow(teams)) cat(sprintf("ROSTERS %d/%d: %s\n",i,nrow(teams),nm))
  old[[i]] <- one_team(tid,nm,2026)
  new[[i]] <- one_team(tid,nm,2027)
  Sys.sleep(0.10)
}
getids <- function(v) v$ids
rows <- lapply(seq_len(nrow(teams)),function(i){
  o<-old[[i]];n<-new[[i]]
  a<-o$ids;b<-n$ids
  ready <- o$status %in% c("OK","EMPTY") && n$status %in% c("OK","EMPTY")
  nr<-length(setdiff(b,a))
  nr_missing<-length(setdiff(a,b))
  ndiff<-length(intersect(a,b))
  tibble(team_id=teams$team_id[i],team_name=teams$team_name[i],
    prior_2026=length(a),current_2027=length(b),
    returning=ndiff,departed=nr_missing,new_athlete_ids=nr,
    roster_exact_same=ready&&length(a)>0&&length(b)>0&&setequal(a,b),
    old_fetch_status=o$status,new_fetch_status=n$status,
    compared=ready,
    status=case_when(
      !ready ~ "FETCH_ERROR_REVIEW",
      length(b)==0 ~ "MISSING_CURRENT_ROSTER",
      length(a)==0 ~ "NO_2026_ROSTER_BASELINE",
      nr==0 && length(a)==length(b) ~ "NO_NEW_IDS_EXACT_SAME",
      nr==0 ~ "NO_NEW_IDS_PARTIAL_OR_STALE",
      nr>=5 && length(b)>=10 ~ "SUBSTANTIAL_REFRESH_SIGNAL",
      TRUE ~ "SOME_NEW_IDS_NOT_PROOF_COMPLETE"
    ),
    old_error=o$error,new_error=n$error,
    current_new_ids=paste(setdiff(b,a),collapse=";")
  )
})
audit<-bind_rows(rows)%>%arrange(team_name)
membership<-bind_rows(lapply(seq_len(nrow(teams)),function(i){
  bind_rows(
    tibble(season=2026,team_id=teams$team_id[i],team_name=teams$team_name[i],athlete_id=old[[i]]$ids),
    tibble(season=2027,team_id=teams$team_id[i],team_name=teams$team_name[i],athlete_id=new[[i]]$ids)
  )
}))
write_csv(audit,file.path(outdir,"team_roster_status_20261018.csv"))
write_csv(membership,file.path(outdir,"season_roster_ids_20261018.csv"))
readiness<-audit%>%filter(compared,old_fetch_status=="OK",new_fetch_status=="OK")
updated <- readiness %>% filter(new_athlete_ids>0)
summary<-list(
  audit_date="2026-10-18",source="hoopR::espn_mbb_teams(year=2027); hoopR::espn_mbb_team_season_roster(season=2026,2027)",
  comparable_to_prior_oct13_metric=TRUE,
  prior_oct13=list(total=365,has_new_athlete_id=133,no_new_athlete_id=232),
  current=list(d1_teams=nrow(teams),successfully_compared=nrow(readiness),
    fetch_errors=sum(!audit$compared),
    missing_current=sum(audit$status=="MISSING_CURRENT_ROSTER"),
    has_new_athlete_id=nrow(updated),
    zero_new_athlete_id=sum(readiness$new_athlete_ids==0),
    exact_same_athlete_ids=sum(readiness$roster_exact_same),
    with_five_or_more_new=sum(readiness$new_athlete_ids>=5),
    substantially_refreshed_signal=sum(readiness$status=="SUBSTANTIAL_REFRESH_SIGNAL"),
    total_new_id_memberships=sum(readiness$new_athlete_ids),
    current_2027_roster_memberships=sum(audit$current_2027)),
  teams_to_inspect=lapply(c("Kansas State","CSUN","Cal State Northridge","Montana","Wisconsin","Washington","Butler","Creighton","St. John's"),function(s) {
     sub<-audit[grepl(s,audit$team_name,ignore.case=TRUE,fixed=TRUE),,drop=FALSE]
     if(nrow(sub)==0) return(list(query=s,found=FALSE))
     lapply(seq_len(nrow(sub)),function(i){
       z<-sub[i,,drop=FALSE]
       list(query=s,school=z$team_name[[1]],previous=z$prior_2026[[1]],current=z$current_2027[[1]],
         returners=z$returning[[1]],new=z$new_athlete_ids[[1]],status=z$status[[1]])
     })
  }),
  interpretation_warnings=c(
    "One newly listed player means progress, not a complete official roster.",
    "Old ESPN season-roster data can be contaminated by historical alumni: compare athlete IDs cautiously; independently verify actual 2027 roster identity before any Portal import.",
    "Roster identities that were never active last year are not necessarily new Division-I freshmen.",
    "This job does not modify production main/Portal data, site, or model."
  ))
write_json(summary,file.path(outdir,"national_summary_20261018.json"),pretty=TRUE,auto_unbox=TRUE)
print(summary$current)
cat("HIGHLIGHT TEAMS\n");print(audit%>%filter(grepl("Kansas State|Montana|Northridge|Wisconsin|Washington|Butler|Creighton|St. John",team_name,ignore.case=TRUE))%>%select(team_name,prior_2026,current_2027,returning,new_athlete_ids,status),n=30)
if(nrow(readiness)<340) stop("Insufficient successful 2026/27 team comparisons: ",nrow(readiness))
cat("AUDIT COMPLETE: outputs isolated to research branch\n")
