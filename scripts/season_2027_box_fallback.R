# Verified 2026-27 ESPN per-game box fallback while SportsDataverse's
# bulk player_box_2027.rds is unavailable. Historical seasons never rewritten.
# Requires hoopR, dplyr, readr, tibble, jsonlite and normalize_ids().
season_2027_box_fallback <- function(scoreboard_fetcher=NULL,box_fetcher=NULL,now=NULL,cache_file=NULL) {
  # Optional dependencies support offline QA; production uses live ESPN.
  or <- function(value, fallback) if(is.null(value)) fallback else value
  path <- if(is.null(cache_file)) "data/espn_2027_verified_game_boxes.csv.gz" else cache_file
  cached <- if(file.exists(path)) {
    normalize_ids(readr::read_csv(path,show_col_types=FALSE))
  } else tibble::tibble()
  seen <- if(nrow(cached)) unique(as.character(cached$game_id)) else character()
  today <- if(is.null(now)) as.Date(format(Sys.time(),tz="America/Chicago",format="%Y-%m-%d")) else as.Date(now)
  start <- as.Date("2026-11-01")
  first <- if(length(seen)) max(start,today-7L) else start
  if(today<start || today>as.Date("2027-05-31"))
    stop("2027 ESPN fallback outside season dates")
  discovered <- list()
  scoreboard_errors <- character()
  for(key in format(seq(first,today,by="day"),"%Y%m%d")) {
    url <- paste0("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=",key,"&groups=50&limit=500")
    doc <- tryCatch(if(is.function(scoreboard_fetcher)) scoreboard_fetcher(key) else jsonlite::fromJSON(url,simplifyVector=FALSE),
      error=function(e) {message("ESPN 2027 scoreboard deferred ",key,": ",conditionMessage(e)); NULL})
    if(is.null(doc) || !is.list(doc$events)) {
      scoreboard_errors <- c(scoreboard_errors,key)
      next
    }
    for(event in doc$events) {
      season <- or(event$season,list())
      year <- suppressWarnings(as.integer(or(season$year,NA)))
      kind <- suppressWarnings(as.integer(or(season$type,NA)))
      competitions <- or(event$competitions,list())
      if(!length(competitions)) next
      comp <- competitions[[1]]
      status <- or(comp$status$type,event$status$type)
      if(is.na(year) || year!=2027L || is.na(kind) || !(kind%in%c(2L,3L)) ||
         !isTRUE(status$completed) || !identical(status$state,"post")) next
      game_id <- as.character(or(event$id,""))
      teams <- or(comp$competitors,list())
      valid <- length(teams)==2 && all(vapply(teams,function(t) {
        !is.null(t$team$id) && !is.null(t$score) &&
        is.finite(suppressWarnings(as.numeric(t$score)))
      },logical(1)))
      if(!grepl("^[0-9]+$",game_id) || !valid) next
      discovered[[game_id]] <- teams
    }
  }
  fetched <- list()
  for(game_id in names(discovered)) {
    # Verified ESPN games remain in cache; avoid re-fetching hundreds of
    # unchanged boxes on busy nights. Corrected final scores are rechecked.
    teams <- discovered[[game_id]]
    ids <- vapply(teams,function(t)as.character(t$team$id),character(1))
    expected <- vapply(teams,function(t)as.numeric(t$score),numeric(1))
    prior <- if(nrow(cached)) cached[as.character(cached$game_id)==game_id,,drop=FALSE] else tibble::tibble()
    if(nrow(prior) && all(c("team_score","team_id")%in%names(prior))) {
      prior_total <- vapply(ids,function(id) {
        rows <- prior[as.character(prior$team_id)==id,,drop=FALSE]
        if(!nrow(rows)) return(NA_real_)
        as.numeric(rows$team_score[[1]])
      },numeric(1))
      if(all(is.finite(prior_total)) && all(prior_total==expected)) next
      message("2027 ESPN final score changed or stale cache for game ",game_id,"; revalidating")
    }
    box <- tryCatch(if(is.function(box_fetcher)) box_fetcher(game_id) else hoopR::espn_mbb_player_box(game_id=as.numeric(game_id)),
      error=function(e){message("2027 ESPN box deferred ",game_id,": ",conditionMessage(e)); NULL})
    if(is.null(box) || nrow(box)<15L) next
    box <- normalize_ids(as_tibble(box))
    required <- c("season","game_id","team_id","athlete_id","points","minutes",
                  "field_goals_made","field_goals_attempted","three_point_field_goals_made",
                  "three_point_field_goals_attempted","free_throws_made","free_throws_attempted",
                  "game_date","opponent_team_display_name")
    if(length(setdiff(required,names(box))) || any(is.na(box$athlete_id)) ||
       any(as.integer(box$season)!=2027L) || length(unique(box$team_id))!=2L) next
    expected <- vapply(discovered[[game_id]],function(t)as.numeric(t$score),numeric(1))
    ids <- vapply(discovered[[game_id]],function(t)as.character(t$team$id),character(1))
    actual <- vapply(ids,function(id)sum(as.numeric(box$points[as.character(box$team_id)==id]),na.rm=TRUE),numeric(1))
    if(!setequal(unique(box$team_id),ids) || !all(actual==expected)) {
      message("2027 ESPN player totals deferred ",game_id,
        " actual=",paste(actual,collapse="-")," final=",paste(expected,collapse="-"))
      next
    }
    if(anyDuplicated(as.character(box$athlete_id)))stop("Duplicate ESPN athlete in final box ",game_id)
    fetched[[game_id]] <- box
  }
  if(!length(fetched) && !nrow(cached))
    stop("No verified 2027 ESPN final player boxes")
  if(length(fetched)) {
    cached <- dplyr::bind_rows(
      if(nrow(cached))dplyr::filter(cached,!(game_id %in% names(fetched)))else tibble::tibble(),
      dplyr::bind_rows(fetched))
  }
  cached <- cached %>% dplyr::distinct(game_id,athlete_id,.keep_all=TRUE) %>%
    dplyr::arrange(game_id,team_id,athlete_id)
  if(nrow(cached)<20L)stop("Less than 20 verified 2027 player game rows")
  if(length(fetched)) {
    dir.create(dirname(path),recursive=TRUE,showWarnings=FALSE)
    readr::write_csv(cached,path,na="")
  }
  missing <- setdiff(names(discovered),unique(as.character(cached$game_id)))
  message("2027 direct ESPN fallback: ESPN final games seen ",length(discovered),
    "; verified in cache ",length(intersect(names(discovered),unique(as.character(cached$game_id)))),
    "; refreshed ",length(fetched),"; missing/deferred ",length(missing),
    "; total cached games ",length(unique(cached$game_id)),
    "; scoreboard errors ",length(scoreboard_errors))
  if(length(missing)) message("WARNING: ESPN completed games not yet verified: ",paste(head(missing,30L),collapse=","))
  if(length(scoreboard_errors)) message("WARNING: ESPN scoreboard unavailable for dates: ",paste(scoreboard_errors,collapse=","))
  cached
}

# Unlike the bulk hoopR RDS, per-game ESPN boxes may be more current.
# Preserve all unrelated bulk games; replace overlapping games atomically.
merge_2027_player_boxes <- function(bulk,direct) {
  if(is.null(direct) || !nrow(direct)) return(bulk)
  if(is.null(bulk) || !nrow(bulk)) return(direct)
  fields <- c("game_id","athlete_id")
  if(length(setdiff(fields,names(bulk))) || length(setdiff(fields,names(direct))))
    stop("Cannot merge 2027 basketball boxes without game and ESPN athlete IDs")
  bulk$game_id <- as.character(bulk$game_id)
  direct$game_id <- as.character(direct$game_id)
  bulk$athlete_id <- as.character(bulk$athlete_id)
  direct$athlete_id <- as.character(direct$athlete_id)
  bulk <- bulk[!(bulk$game_id %in% unique(direct$game_id)),,drop=FALSE]
  dplyr::distinct(dplyr::bind_rows(bulk,direct),game_id,athlete_id,.keep_all=TRUE)
}
