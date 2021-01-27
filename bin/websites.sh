web-check \
    https://trac.einsteintoolkit.org \
    https://cct.lsu.edu \
    https://agaveplatform.org \
    https://togo.agaveplatform.org \
    https://sandbox.agaveplatform.org \
    https://einsteintoolkit.org \
    https://cactuscode.org \
    https://simfactory.org \
    https://stevenrbrandt.com \
    https://svn.einsteintoolkit.org \
    https://accounts.hpc.lsu.edu \
    https://allocations.loni.org \
    https://docs.einsteintoolkit.org \
    https://svn.cct.lsu.edu \
    http://chemoracode.org \
    https://etkhub.ndslabs.org \
    https://melete05.cct.lsu.edu \
    https://tutorial.cct.lsu.edu/etk \
    https://tutorial.cct.lsu.edu/hpx \
    http://tutorial.cct.lsu.edu/ \
    https://build.barrywardell.net/job/EinsteinToolkit
#do
#    echo "checking $w..."
#    curl $w > /dev/null 2>&1
#    if [ $? != 0 ]
#    then
#        curl -k $w > /dev/null 2>&1
#        if [ $? == 0 ]
#        then
#            echo "  -> Cert not valid: $w"
#        else
#            echo "  -> Down: $w"
#        fi
#    fi
#done
