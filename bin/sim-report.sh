HERE=$(pwd)
mkdir -p $HOME/repols
RESULTS=$HOME/repos/testsuite_results
if [  -d $RESULTS ]
then
  cd $RESULTS
  git pull
else
  git clone https://stevenrbrandt@bitbucket.org/einsteintoolkit/testsuite_results.git $RESULTS
fi
SIM=$1
if [ "$SIM" = "" ]
then
    echo "Usage: sim-report.sh sim" >&2
    exit 2
fi
cd $HERE
SIM_DIR=$(./simfactory/bin/sim get-output-dir $SIM 2>/dev/null|tail -1)
if [ "$SIM_DIR" = "" ]
then
    echo "No sim file found" >&2
    exit 1
fi
SIM_FILE="${SIM_DIR}/${SIM}.out"
if [ ! -r "$SIM_FILE" ]
then
    echo "No sim file found: $SIM_FILE" >&2
    exit 1
fi
SIM_MACH=$(./simfactory/bin/sim whoami|cut -d: -f2|cut -d. -f1|sed 's/ //'g)
if [ "$SIM_MACH" = "" ]
then
    echo "Could not locate machine" >&2
    exit 3
fi
grep 'Number \(of\|failed\)' $SIM_FILE
if [ "$?" != 0 ]
then
    echo "Not a testsuite result: $SIM_FILE" >&2
    exit 4
fi
SIM_DIR_PARENT=$(dirname ${SIM_DIR})
SIM_LOG_FILE="${SIM_DIR_PARENT}/log.txt"
if [ ! -r "$SIM_LOG_FILE" ]
then
    echo "log file $SIM_LOG_FILE not found" >&2
    exit 6
fi
grep "'SOURCEDIR':" $SIM_LOG_FILE|grep submitScript|perl -p -e 's/.*\(submitScript\):://'>info.py
THREADS=$(python -c "print(eval(open('info.py','r').read())['NUM_THREADS'])")
HOST=$(python -c "print(eval(open('info.py','r').read())['HOSTNAME'])"|cut -d. -f1)
if [ "$THREADS" = "" ]
then
    echo "THREADS could not be determined" >&2
    exit 7
fi
if [ "$HOST" = "" ]
then
    echo "HOST could not be determined" >&2
    exit 8
fi
set -x
cp $SIM_FILE "$RESULTS/${SIM_MACH}_2_${THREADS}.log"
cd $RESULTS
git status
