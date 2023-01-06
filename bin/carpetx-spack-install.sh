if [ "$SPACK_ROOT" = "" ]
then
    echo 'Please set SPACK_ROOT' >&2
    exit 2
fi
if [ ! -r "$SPACK_ROOT/bin/spack" ]
then
    echo "SPACK_ROOT is set to '$SPACK_ROOT' but '$SPACK_ROOT/bin/spack' was not present." >&2
    echo "Possibly, you need to run this command:" >&2
    echo '  git clone --depth 1 https://github.com/spack/spack.git "$SPACK_ROOT"' >&2
    exit 2
fi
source "$SPACK_ROOT/share/spack/setup-env.sh"

# The Lorene package is broken
cat > "$SPACK_ROOT/var/spack/repos/builtin/packages/lorene/package.py" << EOF
# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import inspect
import os

from spack.package import *


class Lorene(MakefilePackage):
    """LORENE: Langage Objet pour la RElativite NumeriquE.

    LORENE is a set of C++ classes to solve various problems
    arising in numerical relativity, and more generally in
    computational astrophysics. It provides tools to solve
    partial differential equations by means of multi-domain
    spectral methods."""

    homepage = "https://lorene.obspm.fr/index.html"
    cvs = ":pserver:anonymous:anonymous@octane.obspm.fr:/cvsroot%module=Lorene"

    maintainers = ["eschnett"]

    version("2021.4.22", date="2021-04-22")

    variant("fftw", default=True, description="Use external FFTW for spectral transformations")
    variant(
        "bin_star",
        default=True,
        description="Build Bin_star solver for binary neutron star systems",
    )

    depends_on("cvs")
    depends_on("blas")
    depends_on("fftw @3:", when="+fftw")
    depends_on("gsl")
    depends_on("lapack")
    depends_on("pgplot")
    depends_on("cvs")

    parallel = False

    def edit(self, spec, prefix):
        blas_libs = spec["blas"].libs.link_flags
        fftw_incdirs = "-I" + spec["fftw"].prefix.include if "+fftw" in spec else ""
        fftw_libdirs = "-L" + spec["fftw"].prefix.lib if "+fftw" in spec else ""
        fftw_libs = spec["fftw"].libs.link_flags
        gsl_incdirs = "-I" + spec["gsl"].prefix.include
        gsl_libdirs = "-L" + spec["gsl"].prefix.lib
        gsl_libs = spec["gsl"].libs.link_flags
        lapack_libs = spec["lapack"].libs.link_flags
        pgplot_incdirs = "-I" + spec["pgplot"].prefix.include
        pgplot_libdirs = "-L" + spec["pgplot"].prefix.lib
        pgplot_libs = spec["pgplot"].libs.link_flags

        substitutions = [
            ("@CXX@", self.compiler.cxx),
            ("@CXXFLAGS@", "-g -I\$(HOME_LORENE)/C++/Include -O3 -DNDEBUG -Wl,--start-group"),
            ("@CXXFLAGS_G@", "-g -I\$(HOME_LORENE)/C++/Include"),
            ("@F77@", self.compiler.f77),
            ("@F77FLAGS@", "-ffixed-line-length-none -g -O3"),
            ("@F77FLAGS_G@", "-ffixed-line-length-none -g"),
            (
                "@INC@",
                (
                    "-I\$(HOME_LORENE)/C++/Include "
                    + "-I\$(HOME_LORENE)/C++/Include_extra "
                    + fftw_incdirs
                    + " "
                    + gsl_incdirs
                    + " "
                    + pgplot_incdirs
                ),
            ),
            ("@RANLIB@", "ls"),
            ("@MAKEDEPEND@", ": >\$(df).d"),
            ("@FFT_DIR@", "FFTW3"),
            ("@LIB_CXX@", fftw_libdirs + " " + fftw_libs + " -lgfortran"),
            ("@LIB_GSL@", gsl_libdirs + " " + gsl_libs),
            ("@LIB_LAPACK@", lapack_libs + " " + blas_libs),
            ("@LIB_PGPLOT@", pgplot_libdirs + " " + pgplot_libs),
        ]
        local_settings_template = join_path(
            os.path.dirname(inspect.getmodule(self).__file__), "local_settings.template"
        )
        local_settings = join_path(self.stage.source_path, "local_settings")
        copy(local_settings_template, local_settings)
        for key, value in substitutions:
            filter_file(key, value, local_settings)

    def build(self, spec, prefix):
        args = ["HOME_LORENE=" + self.build_directory]
        # (We could build the documentation as well.)
        # (We could circumvent the build system and simply compile all
        # source files, and do so in parallel.)
        make("cpp", "fortran", "export", *args)
        if "+bin_star" in spec:
            with working_dir(join_path("Codes", "Bin_star")):
                make(
                    "-f",
                    "Makefile_O2",
                    "coal",
                    "lit_bin",
                    "init_bin",
                    "coal_regu",
                    "init_bin_regu",
                    "analyse",
                    "prepare_seq",
                    *args
                )

    def install(self, spec, prefix):
        mkdirp(prefix.lib)
        install_tree("Lib", prefix.lib)
        mkdirp(prefix.bin)
        if "+bin_star" in spec:
            for exe in [
                "coal",
                "lit_bin",
                "init_bin",
                "coal_regu",
                "init_bin_regu",
                "analyse",
                "prepare_seq",
            ]:
                install(join_path("Codes", "Bin_star", exe), prefix.bin)

    @property
    def libs(self):
        shared = "+shared" in self.spec
        return find_libraries("liblorene*", root=self.prefix, shared=shared, recursive=True)
EOF

# Ensure we have the compiler set
spack compiler find

spack external find --not-buildable perl diffutils findutils fortran tar xz pkgconf zlib python cuda cvs

grep cuda: ~/.spack/packages.yaml > /dev/null
if [ $? != 0 ]
then
    echo "Spack could not find cuda. Please make sure you've loaded any relevant modules and nvcc is in your PATH." >&2
    exit 1
fi

spack env create carpetx
spack env activate carpetx

spack config add concretizer:unify:true
spack config add concretizer:reuse:true

spack add amrex +cuda cuda_arch=70 ~fortran +hdf5 +openmp +particles
spack add boost cxxstd=17 +filesystem +mpi +system
# spack add cuda @11.5.2 +allow-unsupported-compilers
spack add fftw +mpi +openmp
spack add gperftools
spack add gsl
spack add hdf5 @1.12.1 +cxx +fortran +hl +mpi +threadsafe
spack add hwloc
spack add jpeg
spack add lorene
spack add nsimd @3.0.1
spack add openblas
spack add openpmd-api +python ~hdf5
spack add openssl
spack add mpich
# spack add mpitrampoline
# spack add petsc +cuda +fftw +hwloc +openmp
# spack add reprimand
# Note: HDF5 problems exist with silo @4.11.
spack add silo @4.10.2 ~fortran ~pic ~shared
spack add simulationio +asdf ~python +rnpl +silo
spack add ssht
spack add yaml-cpp
spack add zlib
spack add adios

set -e
spack install --fail-fast
set +e

export NSIMD_DIR=$(spack location -i nsimd)
export NSIMD_ARCH=$(ls $NSIMD_DIR/lib/libnsimd_*.so | perl -p -e 's/.*libnsimd_//'|perl -p -e 's/\.so//')
export VIEW_DIR="$SPACK_ROOT/var/spack/environments/carpetx/.spack-env/view"
export GCC_DIR=$(dirname $(dirname $(which gcc)))
export CUDA_DIR=$(spack location -i cuda)
export DATE=$(date +%m-%d-%Y)

export OPTION_LIST=optionlist.cfg
cat > $OPTION_LIST << EOF
# Option list for the Einstein Toolkit

# The "weird" options here should probably be made the default in the
# ET instead of being set here.

# Whenever this version string changes, the application is configured
# and rebuilt from scratch
VERSION = Spack-${DATE}

CPP = ${GCC_DIR}/bin/cpp
FPP = ${GCC_DIR}/bin/cpp
CC = ${GCC_DIR}/bin/gcc
CXX = ${CUDA_DIR}/bin/nvcc --compiler-bindir ${GCC_DIR}/bin/g++ -x cu
FC = ${GCC_DIR}/bin/gfortran
F90 = ${GCC_DIR}/bin/gfortran
LD = ${CUDA_DIR}/bin/nvcc --compiler-bindir ${GCC_DIR}/bin/g++

CPPFLAGS = -DSIMD_CPU
CFLAGS = -pipe -g -march=native 
# - We use "--relocatable-device-code=true" to allow building with
#   debug versions of AMReX
#   <https://github.com/AMReX-Codes/amrex/issues/1829>
# - We use "--objdir-as-tempdir" to prevent errors such as
#   Call parameter type does not match function signature!
#     %tmp = load double, double* %x.addr, align 8, !dbg !1483
#     float  %1 = call i32 @__isnanf(double %tmp), !dbg !1483
CXXFLAGS = -pipe -g --compiler-options -march=native -std=c++17 --compiler-options -std=gnu++17 --expt-relaxed-constexpr --extended-lambda --gpu-architecture sm_70 --forward-unknown-to-host-compiler --Werror ext-lambda-captures-this --relocatable-device-code=true --objdir-as-tempdir
FPPFLAGS = -traditional
F90FLAGS = -pipe -g -march=native -fcray-pointer -ffixed-line-length-none
LDFLAGS = -Wl,-rpath,${VIEW_DIR}/targets/x86_64-linux/lib -Wl,-rpath,/usr/local/lib -Wl,-rpath,/usr/local/nvidia/lib64
LIBS = nvToolsExt

C_LINE_DIRECTIVES = yes
F_LINE_DIRECTIVES = yes

DEBUG = no
CPP_DEBUG_FLAGS = -DCARPET_DEBUG
C_DEBUG_FLAGS = -fbounds-check -fsanitize=undefined -fstack-protector-all -ftrapv
CXX_DEBUG_FLAGS = -fbounds-check -fsanitize=undefined -fstack-protector-all -ftrapv -lineinfo
FPP_DEBUG_FLAGS = -DCARPET_DEBUG
F90_DEBUG_FLAGS = -fcheck=bounds,do,mem,pointer,recursion -finit-character=65 -finit-integer=42424242 -finit-real=nan -fsanitize=undefined -fstack-protector-all -ftrapv

OPTIMISE = yes
C_OPTIMISE_FLAGS = -O3 -fcx-limited-range -fexcess-precision=fast -fno-math-errno -fno-rounding-math -fno-signaling-nans -funsafe-math-optimizations
CXX_OPTIMISE_FLAGS = -O3 -fcx-limited-range -fexcess-precision=fast -fno-math-errno -fno-rounding-math -fno-signaling-nans -funsafe-math-optimizations
F90_OPTIMISE_FLAGS = -O3 -fcx-limited-range -fexcess-precision=fast -fno-math-errno -fno-rounding-math -fno-signaling-nans -funsafe-math-optimizations

OPENMP = yes
CPP_OPENMP_FLAGS = -fopenmp
FPP_OPENMP_FLAGS = -D_OPENMP

WARN = yes

DISABLE_INT16 = yes
DISABLE_REAL16 = yes

VECTORISE = no

ADIOS2_DIR = ${VIEW_DIR}
AMREX_DIR = ${VIEW_DIR}
ASDF_CXX_DIR = ${VIEW_DIR}
BOOST_DIR = ${VIEW_DIR}
FFTW3_DIR = ${VIEW_DIR}
GSL_DIR = ${VIEW_DIR}
HDF5_DIR = ${VIEW_DIR}
HDF5_ENABLE_CXX = yes
HDF5_ENABLE_FORTRAN = yes
HDF5_INC_DIRS = ${VIEW_DIR}/include
HDF5_LIB_DIRS = ${VIEW_DIR}/lib
HDF5_LIBS = hdf5_hl_cpp hdf5_cpp hdf5_hl_f90cstub hdf5_f90cstub hdf5_hl_fortran hdf5_fortran hdf5_hl hdf5
HDF5_ENABLE_CXX = yes
HPX_DIR = ${VIEW_DIR}
HWLOC_DIR = ${VIEW_DIR}
JEMALLOC_DIR = ${VIEW_DIR}
LORENE_DIR = ${VIEW_DIR}
MPI_DIR = ${VIEW_DIR}
MPI_INC_DIRS = ${VIEW_DIR}/include
MPI_LIB_DIRS = ${VIEW_DIR}/lib
MPI_LIBS = mpi
NSIMD_DIR = ${VIEW_DIR}
NSIMD_INC_DIRS = ${VIEW_DIR}/include
NSIMD_LIB_DIRS = ${VIEW_DIR}/lib
NSIMD_ARCH = ${NSIMD_ARCH}
NSIMD_SIMD = ${NSIMD_ARCH}
OPENBLAS_DIR = ${VIEW_DIR}
OPENPMD_API_DIR = ${VIEW_DIR}
OPENPMD_DIR = ${VIEW_DIR}
OPENSSL_DIR = ${VIEW_DIR}
#PETSC_DIR = ${VIEW_DIR}
#PETSC_ARCH_LIBS = m
PTHREADS_DIR = NO_BUILD
#REPRIMAND_DIR = ${VIEW_DIR}
#REPRIMAND_LIBS = RePrimAnd
RNPLETAL_DIR = ${VIEW_DIR}
SILO_DIR = ${VIEW_DIR}
SIMULATIONIO_DIR = ${VIEW_DIR}
SSHT_DIR = ${VIEW_DIR}
YAML_CPP_DIR = ${VIEW_DIR}
ZLIB_DIR = ${VIEW_DIR}
EOF
echo Optionlist created: $OPTION_LIST
