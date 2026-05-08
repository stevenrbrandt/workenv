URL=$(git config -l | grep 'remote.origin.url=' | cut -d= -f2)
USER=$(echo $URL | cut -d/ -f4)
REPO=$(echo $URL | cut -d/ -f5)
echo "git remote set-url origin git@github.com:${USER}/${REPO}.git"
