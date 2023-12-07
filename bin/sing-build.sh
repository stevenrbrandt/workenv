if [ "$1" = "" ]
then
    echo "$0 image-name [src-name]" >&2
    exit 2
fi
simg=$1
if [ "$2" = "" ]
then
    src=$1
else
    src=$2
fi
set -x
trun srun -p gpu -A $ACCOUNT -n 1 --cpus-per-task 24 singularity build -F /work/sbrandt/images/$simg.simg docker://stevenrbrandt/$src
chgrp singularity /work/sbrandt/images/$1.simg
hostname
