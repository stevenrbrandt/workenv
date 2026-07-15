if [ "$1" != "" ]; then
    URL="$1"
else
    URL=$(git config -l | grep 'remote.origin.url=' | cut -d= -f2)
fi
if grep https > /dev/null <<< "${URL}"
then
    USER=$(echo $URL | cut -d/ -f4)
    REPO=$(echo $URL | cut -d/ -f5)
else
    USER=$(echo $URL | cut -d: -f2 | cut -d/ -f1)
    REPO=$(echo $URL | cut -d: -f2 | cut -d/ -f2)
fi
if grep bitbucket > /dev/null <<< "${URL}" 
then
    echo "git remote set-url origin git@bitbucket.com:${USER}/${REPO}"
    echo "git remote set-url origin https://bitbucket.com/${USER}/${REPO}"
else
    echo "git remote set-url origin git@github.com:${USER}/${REPO}"
    echo "git remote set-url origin https://github.com/${USER}/${REPO}"
fi
