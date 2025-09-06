alias envon 'set _ev=`\envon \!*` \
if ( $status == 0 ) then \
    eval "$_ev" \
    if ( $status != 0 && $#argv >= 1 ) then \
        switch ("$1") \
        case "help": \
        case "-h": \
        case "--help": \
        case "--install": \
        case "-*": \
            \envon \!* \
            breaksw \
        endsw \
    endif \
else if ( $#argv >= 1 ) then \
    switch ("$1") \
    case "help": \
    case "-h": \
    case "--help": \
    case "--install": \
    case "-*": \
        \envon \!* \
        breaksw \
    endsw \
endif \
unset _ev'