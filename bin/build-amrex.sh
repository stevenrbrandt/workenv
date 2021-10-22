(
set -xe
export MPIEXEC_EXECUTABLE=$(which mpiexec)
export INSTALL_DIR=/project/$USER/install
export BUILD_DIR=/project/$USER/build
export SRC_DIR=$HOME/repos/amrex
BUILDID=2
if [ $BUILDID = 1 ]
then
    CUDA=OFF
else
    CUDA=ON
fi
echo "CUDA is $CUDA"
sleep 5
spack load gcc@9.4.0 cuda mpich%gcc@9.4.0 cmake%gcc@9.4.0
#rm -fr ~/repos/amrex/build${BUILDID}
mkdir -p $BUILD_DIR/amrex-build${BUILDID}
cd $BUILD_DIR/amrex-build${BUILDID}
mkdir -p $INSTALL_DIR
BUILD_TYPE=Debug
ASSERTS=Off
if [ $CUDA = ON ]
then
  cmake -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
    -DAMReX_PARTICLES=ON \
    -DAMReX_ASSERTIONS=$ASSERTS \
    -DAMReX_FORTRAN=ON \
    -DAMReX_CUDA=$CUDA \
    -DAMReX_GPU_BACKEND=CUDA \
    -DAMReX_PIC=ON \
    -DAMReX_OMP=ON \
    -DAMReX_MPI=ON \
    -DCMAKE_C_COMPILER=$(which mpicc) \
    -DCMAKE_CXX_COMPILER=$(which mpicxx) \
    -DMPIEXEC_EXECUTABLE=$MPIEXEC_EXECUTABLE \
    -DCMAKE_CUDA_COMPILER=$(which nvcc) \
    -DCMAKE_INSTALL_PREFIX=$INSTALL_DIR/amrex${BUILDID} \
    -DAMREX_GPUS_PER_NODE=1 \
    $SRC_DIR |& tee ~/amrex-config${BUILDID}-log.txt
else
  cmake -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
    -DAMReX_PARTICLES=ON \
    -DAMReX_ASSERTIONS=$ASSERTS \
    -DAMReX_FORTRAN=ON \
    -DAMReX_CUDA=$CUDA \
    -DAMReX_PIC=ON \
    -DAMReX_OMP=ON \
    -DAMReX_MPI=ON \
    -DCMAKE_C_COMPILER=$(which mpicc) \
    -DCMAKE_CXX_COMPILER=$(which mpicxx) \
    -DMPIEXEC_EXECUTABLE=$MPIEXEC_EXECUTABLE \
    -DCMAKE_INSTALL_PREFIX=$INSTALL_DIR/amrex${BUILDID} \
    $SRC_DIR |& tee ~/amrex-config${BUILDID}-log.txt
fi
make -j6 install
) |& tee ~/amrex-build${BUILDID}-log.txt
