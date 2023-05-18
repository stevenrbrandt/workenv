HERE=$PWD
set -ex
if [ ! -r GetComponents ]
then
  curl -LO https://raw.githubusercontent.com/gridaphobe/CRL/master/GetComponents
  chmod a+x GetComponents
fi
if [ ! -r einsteintoolkit.th ]
then
  curl -LO https://bitbucket.org/einsteintoolkit/manifest/raw/master/einsteintoolkit.th
fi
if [ ! -d Cactus ]
then
  ./GetComponents --parallel --shallow einsteintoolkit.th
fi
cd Cactus
if [ ! -r repos/simfactory2/etc/defs.local.ini ]
then
  ./simfactory/bin/sim setup-silent
  echo "[$(./simfactory/bin/sim whoami|cut -d: -f2|sed 's/\s//')]" >> simfactory/etc/defs.local.ini
  echo "sourcebasedir=$(dirname $(pwd))" >> simfactory/etc/defs.local.ini
fi
trun ./simfactory/bin/sim build sim-cpu -j10 --thornlist $HERE/einsteintoolkit.th |& tee $HERE/make.out
