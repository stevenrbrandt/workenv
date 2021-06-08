if [ "$SPACK_ROOT" = "" ]
then
    echo "SPACK_ROOT is not set" >&2
    exit 2
fi

if [ ! -d "$SPACK_ROOT" ]
then
    git clone https://github.com/spack/spack.git "$SPACK_ROOT"
    spack external find
fi
