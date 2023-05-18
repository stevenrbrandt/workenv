THREADS=1
PROCS=$((2*$THREADS))
MACH=$(./simfactory/bin/sim whoami|cut -d: -f2|sed 's/ //g')
TEST=${MACH}__${PROCS}_${THREADS}
TEST=the-test2
USER=$(id -n -u)
SIMULATIONS=$(cat simfactory/mdb/machines/db1.hpc.lsu.edu.ini |grep '^basedir\>'|cut -d= -f2|sed 's/ //g'|sed "s/@USER@/$USER/")
echo "SIM DIR: ${SIMULATIONS}"
if [ -d ${SIMULATIONS}/${TEST} ]
then
    echo "The test '${TEST}' was run"
else
    echo "The test '${TEST}' was NOT run"
    ./simfactory/bin/sim create-run --procs=$PROCS --ppn-used=$PROCS --num-threads=$THREADS --config=sim-cpu --testsuite ${TEST}
fi
cd ${SIMULATIONS}/${TEST}/output-0000
if [ ! -d testsuite_results ]
then
git clone --depth 1 https://stevenrbrandt@bitbucket.org/einsteintoolkit/testsuite_results.git 
fi
ls testsuite_results/results
pwd
set -x
cp ${TEST}.out testsuite_results/results/${MACH}__${PROCS}_${THREADS}.log
cd testsuite_results
ls results
git add results/${MACH}__${PROCS}_${THREADS}.log
git status 
git commit -m "$Test for ${MACH} added"
git push
