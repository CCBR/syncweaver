args <- commandArgs(trailingOnly = TRUE)
entry_script <- args[[1]]
repository <- args[[2]]
release_tag <- args[[3]]
previous_tag <- args[[4]]
package_name <- args[[5]]

if (nzchar(package_name)) {
  result <- functracer::trace_release_impact(
    entry_script = entry_script,
    repository = repository,
    release_tag = release_tag,
    previous_tag = previous_tag,
    package_name = package_name
  )
} else {
  result <- functracer::trace_release_impact(
    entry_script = entry_script,
    repository = repository,
    release_tag = release_tag,
    previous_tag = previous_tag
  )
}

if (isTRUE(result$script_affected)) {
  cat("true")
} else {
  cat("false")
}
