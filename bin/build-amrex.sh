(
set -x
mkdir -p ~/repos/amrex/build
cd ~/repos/amrex/build
mkdir -p ~/install
cmake -DCMAKE_BUILD_TYPE=Debug \
  -DAMReX_PARTICLES=OFF \
  -DAMReX_ASSERTIONS=ON \
  -DAMReX_FORTRAN=OFF \
  -DAMReX_CUDA=ON \
  -DAMReX_GPU_BACKEND=CUDA \
  -DAMReX_PIC=ON \
  -DAMReX_OMP=ON \
  -DAMReX_MPI=ON \
  -DAMReX_TUTORIALS=OFF \
  -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_INSTALL_PREFIX=$HOME/install/amrex \
  -DAMREX_GPUS_PER_NODE=1 \
  ..
make -j6 install
) 2>&1 | tee ~/amrex-build-log.txt
