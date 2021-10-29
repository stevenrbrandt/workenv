(
set -xe
export BUILDID=1
export BUILD_TYPE=RelWithDebugInfo
export MPIEXEC_EXECUTABLE=$(which mpiexec)
export INSTALL_DIR=/project/$USER/install${BUILDID}${BUILD_TYPE}
export BUILD_DIR=/project/$USER/build${BUILDID}${BUILD_TYPE}
export SRC_DIR=$HOME/repos/amrex
if [ $BUILDID = 2 ]
then
    CUDA=OFF
else
    CUDA=ON
fi
echo "CUDA is $CUDA"
sleep 5
spack load gcc@9.4.0 cuda mpich%gcc@9.4.0 cmake%gcc@9.4.0
rm -fr $BUILD_DIR $INSTALL_DIR
mkdir -p $BUILD_DIR $INSTALL_DIR
cd $BUILD_DIR
if [ $CUDA = ON ]
then
  cmake -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
    -DAMReX_PARTICLES=ON \
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
    -DCMAKE_INSTALL_PREFIX=$INSTALL_DIR \
    -DAMREX_GPUS_PER_NODE=2 \
    $SRC_DIR |& tee ~/amrex-config${BUILDID}-log.txt
else
  cmake -DCMAKE_BUILD_TYPE=$BUILD_TYPE \
    -DAMReX_PARTICLES=ON \
    -DAMReX_FORTRAN=ON \
    -DAMReX_CUDA=$CUDA \
    -DAMReX_PIC=ON \
    -DAMReX_OMP=ON \
    -DAMReX_MPI=ON \
    -DCMAKE_C_COMPILER=$(which mpicc) \
    -DCMAKE_CXX_COMPILER=$(which mpicxx) \
    -DMPIEXEC_EXECUTABLE=$MPIEXEC_EXECUTABLE \
    -DCMAKE_INSTALL_PREFIX=$INSTALL_DIR \
    $SRC_DIR |& tee ~/amrex-config${BUILDID}-log.txt
fi
make -j6 install
) |& tee /project/sbrandt/amrex-build${BUILDID}-log.txt
