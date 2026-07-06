URL=$(git config -l | grep 'remote.origin.url=' | cut -d= -f2)
USER=$(echo $URL | cut -d/ -f4)
REPO=$(echo $URL | cut -d/ -f5)
if grep bitbucket > /dev/null <<< "${URL}" 
then
    echo "git remote set-url origin git@bitbucket.com:${USER}/${REPO}"
else
    echo "git remote set-url origin git@github.com:${USER}/${REPO}.git"
fi
