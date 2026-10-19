#!/usr/bin/env Rscript
# Probe whether team-roster site-v2 bios align to ESPN's truly season-specific
# core-v2 roster memberships before collecting the entire NCAA.
suppressPackageStartupMessages({library(hoopR);library(dplyr);library(tibble);library(jsonlite)})
teams <- hoopR::espn_mbb_teams(year=2027)%>%
  mutate(team_id=as.character(team_id))
patterns<-c("Kansas State","Montana Grizzlies","Cal State Northridge",
            "North Dakota State","McNeese")
data<-list()
for(pattern in patterns) {
  t <- teams%>%filter(grepl(pattern,display_name,ignore.case=TRUE,fixed=TRUE))%>%
    slice(1)
  if(nrow(t)!=1) stop("Missing team query ",pattern)
  id<-t$team_id[[1]]
  a<-hoopR::espn_mbb_team_season_roster(team_id=id,season=2027)
  b<-hoopR::espn_mbb_team_roster(team_id=id,season=2027)
  if(!"athlete_id" %in% names(b))stop("Site roster missing athlete_id")
  s<-unique(as.character(a$athlete_id))
  m<-intersect(s,unique(as.character(b$athlete_id)))
  row<-list(team_name=t$display_name[[1]],team_id=id,
    season_roster_members=length(s),site_bio_rows=nrow(b),matched_ids=length(m),
    match_coverage=length(m)/max(1,length(s)),
    site_columns=as.list(names(b)),
    names_sample=if("full_name" %in% names(b)) as.list(head(b$full_name,6)) else NULL)
  data[[pattern]]<-row
  cat(pattern," season=",length(s)," bios=",nrow(b),
      " matches=",length(m),"\n")
}
dir.create("research_qa/roster_integration",recursive=TRUE,showWarnings=FALSE)
jsonlite::write_json(list(date="2026-10-19",source="hoopR ESPN site and core-v2",
  teams=data,
  warning="Season-specific core-v2 membership required. Site-v2 bios are never sufficient by themselves for team membership."),
  "research_qa/roster_integration/roster_bio_probe.json",pretty=TRUE,auto_unbox=TRUE)
