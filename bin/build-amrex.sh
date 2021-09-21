(
set -xe
export MPIEXEC_EXECUTABLE=$(which mpiexec)
BUILDID=1
if [ $BUILDID = 1 ]
then
    CUDA=OFF
else
    CUDA=ON
fi
echo "CUDA is $CUDA"
sleep 5
spack load gcc@9.4.0 cuda mpich%gcc@9.4.0 cmake%gcc@9.4.0
rm -fr ~/repos/amrex/build${BUILDID}
mkdir -p ~/repos/amrex/build${BUILDID}
cd ~/repos/amrex/build${BUILDID}
mkdir -p ~/install
if [ $CUDA = ON ]
then
  cmake -DCMAKE_BUILD_TYPE=Release \
    -DAMReX_PARTICLES=ON \
    -DAMReX_ASSERTIONS=Off \
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
    -DCMAKE_INSTALL_PREFIX=$HOME/install/amrex${BUILDID} \
    -DAMREX_GPUS_PER_NODE=1 \
    .. |& tee ~/amrex-config${BUILDID}-log.txt
else
  cmake -DCMAKE_BUILD_TYPE=Release \
    -DAMReX_PARTICLES=ON \
    -DAMReX_ASSERTIONS=Off \
    -DAMReX_FORTRAN=ON \
    -DAMReX_CUDA=$CUDA \
    -DAMReX_PIC=ON \
    -DAMReX_OMP=ON \
    -DAMReX_MPI=ON \
    -DCMAKE_C_COMPILER=$(which mpicc) \
    -DCMAKE_CXX_COMPILER=$(which mpicxx) \
    -DMPIEXEC_EXECUTABLE=$MPIEXEC_EXECUTABLE \
    -DCMAKE_INSTALL_PREFIX=$HOME/install/amrex${BUILDID} \
    .. |& tee ~/amrex-config${BUILDID}-log.txt
fi
make -j6 install
) |& tee ~/amrex-build${BUILDID}-log.txt
