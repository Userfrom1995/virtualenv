alias envon 'if ( $#argv >= 0 ) then; switch ("$1") \
case "help": \
case "-h": \
case "--help": \
case "--install": \
case "-*": \
    \envon \!*; breaksw; \
default: \
    set _ev=`\envon \!*` && eval "$_ev" && unset _ev; breaksw; \
endsw \
endif'