if [ "$SPACK_ROOT" = "" ]
then
    echo "SPACK_ROOT is not set" >&2
    exit 2
fi

if [ ! -d "$SPACK_ROOT" ]
then
    git clone --depth 1 https://github.com/spack/spack.git "$SPACK_ROOT"

    rm -fr ~/.spack
    source $SPACK_ROOT/share/spack/setup-env.sh

    which module
    if [ $? = 0 ]
    then
        module purge
        module load gcc/11.2.0
        module load cuda/12.1.1
        #module load python/3.7.6
    fi
    spack compiler find
    spack external find --not-buildable perl cuda diffutils findutils tar xz curl pkgconf zlib gmake git # python
fi
