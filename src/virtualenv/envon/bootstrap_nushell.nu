# envon bootstrap for nushell
def --env envon [...args] {
  if ($args | is-empty) == false {
    let first = ($args | first)
    if $first == '--' { let args = ($args | skip 1); ^envon ...$args; return }
    if ($first == 'help') or ($first == '-h') or ($first == '--help') or ($first == '--install') or (($first | str starts-with '-') == true) {
      ^envon ...$args; return
    }
  }
  let venv = (^envon --print-path ...$args | str trim)
  if ($venv | is-empty) { return }
  let is_windows = ($nu.os-info.name == 'windows')
  let act = (if $is_windows { ($venv | path join 'Scripts' 'activate.nu') } else { ($venv | path join 'bin' 'activate.nu') })
  if ($act | path exists) { overlay use $act }
}
