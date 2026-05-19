TIMER_THING_HOST=$(hostname -s)
TIMER_THING_LONG_TIME=60
TIMER_THING_CMD=""
TIMER_THING_EXIT_CODE=""
TIMER_THING_TIME=""
TIMER_THING_START=$SECONDS
TIMER_THING_READY=0
TIMER_THING_NO_MESSAGE=" vi vim ed nano ssh tmux screen vimdiff top git "
__timer_thing_start__() {
    if [ $TIMER_THING_READY = 0 ]
    then
        if [ "${BASH_COMMAND}" != "__timer_thing_end__" ]
        then
            TIMER_THING_CMD="${BASH_COMMAND}"
            TIMER_THING_START=$SECONDS
            TIMER_THING_READY=1
        fi
    fi
}
__timer_thing_end__() {
    if [ $TIMER_THING_READY = 1 ]
    then
        TIMER_THING_READY=0
        TIMER_THING_EXIT_CODE=$?
        TIMER_THING_TIME=$(($SECONDS - $TIMER_THING_START))
        TIMER_THING_MESSAGE="[$TIMER_THING_HOST:$PWD] $TIMER_THING_CMD => $TIMER_THING_EXIT_CODE (${TIMER_THING_TIME}s)" 
        if [ $TIMER_THING_TIME -gt $TIMER_THING_LONG_TIME ]
        then
            TIMER_THING_CMD_1=${TIMER_THING_CMD%% *}
            if ! echo $TIMER_THING_NO_MESSAGE | grep -qw "$TIMER_THING_CMD_1"; then
                telegram-send "$TIMER_THING_MESSAGE"
            fi
        fi
    fi
}
trap __timer_thing_start__ DEBUG
export PROMPT_COMMAND="__timer_thing_end__"
