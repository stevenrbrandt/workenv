#!/bin/sh
# Usage:
# command="bin/auth-cmd.sh",from="shelob?,shelob???,mike?,mike???,*.hpc.lsu.edu" ssh-dss AAAAB3NzaC1kc3MAAA...
# Put the full path to a singularity image in the file $HOME/sing.txt.
if [ -r $HOME/work/sing.txt ]
then
    IMAGE=$(cat $HOME/work/sing.txt)
fi
if ! which singularity 2>/dev/null
then
    IMAGE=''
fi
if [ "$IMAGE" != "" ]
then
    if [ -r "$IMAGE" ]
    then
        # If the SINGULARITY_CONTAINER variable is set,
        # then we are already in the container
        if [ "$SINGULARITY_CONTAINER" = "" ]
        then
            # Switch to running inside singularity
            if [ "$SSH_ORIGINAL_COMMAND" = "" ]
            then
                exec singularity exec $SING_OPTS $IMAGE bash --login
            else
                exec singularity exec $SING_OPTS $IMAGE bash --login -c "$SSH_ORIGINAL_COMMAND"
            fi
        fi
    fi
fi

if [ -n "$SINGULARITY_CONTAINER" ];
then
  #env > ~/.login.singularity.env-$(date +%s)
  /bin/true
else
  #env > ~/.login.ssh.env-$(date +%s)
  if [ -n "$SSH_ORIGINAL_COMMAND" ]; then
    bash --login -c "$SSH_ORIGINAL_COMMAND"
  else
    bash --login
  fi
fi
