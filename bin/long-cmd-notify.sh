TIMER_THING_HOST=$(hostname -s)
TIMER_THING_CMD=""
TIMER_THING_READY=0

__timer_thing_set_title__() {
    printf '\033]0;%s\007' "$1"
}

__timer_thing_start__() {
    if [ $TIMER_THING_READY = 0 ]
    then
        if [ "${BASH_COMMAND}" != "__timer_thing_end__" ]
        then
            TIMER_THING_CMD="${BASH_COMMAND}"
            TIMER_THING_READY=1
            __timer_thing_set_title__ "⏳ $TIMER_THING_CMD"
        fi
    fi
}

__timer_thing_end__() {
    TIMER_THING_EXIT_CODE=$?
    if [ $TIMER_THING_READY = 1 ]
    then
        TIMER_THING_READY=0
    fi
    __timer_thing_set_title__ "✅ $TIMER_THING_HOST:$PWD"
    return $TIMER_THING_EXIT_CODE
}

trap __timer_thing_start__ DEBUG
export PROMPT_COMMAND="__timer_thing_end__"
