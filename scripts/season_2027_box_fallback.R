# Verified 2026-27 ESPN per-game box fallback while SportsDataverse's
# bulk player_box_2027.rds is unavailable. Historical seasons never rewritten.
# Requires hoopR, dplyr, readr, tibble, jsonlite and normalize_ids().
season_2027_box_fallback <- function() {
  or <- function(value, fallback) if(is.null(value)) fallback else value
  path <- "data/espn_2027_verified_game_boxes.csv.gz"
  cached <- if(file.exists(path)) {
    normalize_ids(readr::read_csv(path,show_col_types=FALSE))
  } else tibble::tibble()
  seen <- if(nrow(cached)) unique(as.character(cached$game_id)) else character()
  today <- as.Date(format(Sys.time(),tz="America/Chicago",format="%Y-%m-%d"))
  start <- as.Date("2026-11-01")
  first <- if(length(seen)) max(start,today-7L) else start
  if(today<start || today>as.Date("2027-05-31"))
    stop("2027 ESPN fallback outside season dates")
  discovered <- list()
  scoreboard_errors <- character()
  for(key in format(seq(first,today,by="day"),"%Y%m%d")) {
    url <- paste0("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=",key,"&groups=50&limit=500")
    doc <- tryCatch(jsonlite::fromJSON(url,simplifyVector=FALSE),
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
    box <- tryCatch(hoopR::espn_mbb_player_box(game_id=as.numeric(game_id)),
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
  message("2027 direct ESPN fallback verified ",length(unique(cached$game_id)),
    " games / ",nrow(cached)," player-games; refreshed ",length(fetched),
    "; scoreboard errors ",length(scoreboard_errors))
  cached
}
