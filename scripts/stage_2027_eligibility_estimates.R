#!/usr/bin/env Rscript
# RESEARCH ONLY. 2027 current ESPN roster eligibility estimates for 2027-28
# recruiting target. No source of NCAA eligibility adjudication exists here;
# this is a planning estimate using an assumed five-season window starting at
# earliest archived Division I appearance. This is not an NCAA eligibility ruling.
# Staff overrides in the Portal always supersede these public factual estimates.
suppressPackageStartupMessages({
 library(dplyr);library(readr);library(jsonlite)
})
root<-"research_data/staged"
roster_csv<-file.path(root,"current_roster_2027_identity.csv")
historical_csv<-file.path(root,"player_seasons_2020_2026.csv.gz")
roster_json<-file.path(root,"current_roster_2027_candidate.json")
qa_dir<-"research_qa/roster_integration"
stopifnot(file.exists(roster_csv),file.exists(historical_csv),file.exists(roster_json))
historical<-read_csv(historical_csv,show_col_types=FALSE,
                     col_types=cols(.default=col_character()))
roster<-read_csv(roster_csv,show_col_types=FALSE,
                 col_types=cols(.default=col_character()))
history_rollup<-historical%>%group_by(athlete_id)%>%
 summarise(first_stat_season=min(as.integer(season)),
           last_stat_season=max(as.integer(season)),
           observed_stat_seasons=n_distinct(season),.groups="drop")
joined<-roster%>%left_join(history_rollup,by="athlete_id",relationship="many-to-one")%>%
 mutate(
  # ESPN records label 2026-27 as NCAA ending year 2027.
  # Under the user's five-year planning maximum, a 2026-27 freshman
  # is estimated to have four years left for 2027-28.
  eligibility_estimate=pmax(0L,pmin(4L,
    4L-(2027L-coalesce(first_stat_season,2027L)))),
  eligibility_basis=if_else(
    is.na(first_stat_season),"NO_DIVISION_I_STATS_FRESHMAN_PROXY",
    "FIRST_OBSERVED_DI_BOX_SEASON_PROXY"),
  eligibility_confidence="LOW__STAFF_REVIEW_RECOMMENDED",
  eligibility_target="2027-28"
 )
if(nrow(joined)!=5456L || anyDuplicated(joined$athlete_id) ||
   any(is.na(joined$eligibility_estimate)) ||
   any(joined$eligibility_estimate<0|joined$eligibility_estimate>4))
  stop("Invalid roster estimate cardinality or eligibility range")
payload<-fromJSON(roster_json,simplifyVector=FALSE)
if(length(payload$players)!=nrow(joined)||payload$rosterSeason!=2027)
 stop("Candidate roster JSON count or season drift")
index<-setNames(seq_len(nrow(joined)),joined$athlete_id)
for(i in seq_along(payload$players)){
 athlete_id<-as.character(payload$players[[i]]$espnAthleteId)
 j<-index[[athlete_id]]
 if(is.null(j))stop("Missing ESPN ID in historical join: ",athlete_id)
 row<-joined[j,,drop=FALSE]
 payload$players[[i]]$eligibilityEstimate<-as.integer(row$eligibility_estimate[[1]])
 payload$players[[i]]$eligibilityTargetSeason<-"2027-28"
 payload$players[[i]]$eligibilityEstimateBasis<-as.character(row$eligibility_basis[[1]])
 payload$players[[i]]$firstSeasonWithStats<-if(is.na(row$first_stat_season[[1]])) NULL else as.integer(row$first_stat_season[[1]])
 payload$players[[i]]$eligibilityConfidence<-"Low - staff editable"
}
payload$eligibilityMethod<-"Five-season maximum planning proxy from first archived D-I box season, default 4 for no D-I history. Actual eligibility may differ due to redshirts, transfers, waivers, international/lower-level play; editable staff corrections take precedence."
payload$eligibilityTargetSeason<-"2027-28"
write_json(payload,roster_json,pretty=FALSE,auto_unbox=TRUE,na="null",null="null")
write_csv(joined,file.path(root,"current_roster_2027_identity_estimated.csv"))
counts<-as.list(as.integer(table(factor(joined$eligibility_estimate,levels=0:4))))
names(counts)<-as.character(0:4)
qa<-list(status="PASS",roster_players=nrow(joined),
 target_season="2027-28",source_2027_roster=TRUE,
 all_players_estimated=all(!is.na(joined$eligibility_estimate)),
 estimate_counts_0_to_4=counts,
 no_di_history=sum(is.na(joined$first_stat_season)),
 no_di_history_estimate_four=sum(is.na(joined$first_stat_season)&joined$eligibility_estimate==4L),
 with_earliest_DI_stats=sum(!is.na(joined$first_stat_season)),
 user_eligibility_overrides_remain_authoritative=TRUE,
 no_eligibility_unknown_in_payload=TRUE,
 no_staff_data_changed=TRUE,
 estimate_is_not_NCAA_certification=TRUE,
 roster_json_bytes=file.info(roster_json)$size)
dir.create(qa_dir,recursive=TRUE,showWarnings=FALSE)
write_json(qa,file.path(qa_dir,"eligibility_estimates_2027_28_qa.json"),pretty=TRUE,auto_unbox=TRUE)
print(qa)
