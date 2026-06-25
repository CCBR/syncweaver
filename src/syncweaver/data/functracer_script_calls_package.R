args <- commandArgs(trailingOnly = TRUE)
entry_script <- args[[1]]
package_dir <- args[[2]]

result <- functracer::analyze_dependencies(
  entry_script = entry_script,
  package_dir = package_dir
)

if (NROW(result) > 0) {
  cat("true")
} else {
  cat("false")
}
