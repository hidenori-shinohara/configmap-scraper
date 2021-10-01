# kubectlutil

A script to make it easy to monitor supercluster jobs.

## Configmap
Example: `python3 ~/kubectlutil/kubectlutil.py --namespace hidenori --kubeconfig ~/.kube/config configmap -n satoshipay-io-1`

This prints the readable, formatted configmap for the node `satoshipay-io-1`.

## HTTP endpoint
Example: `python3 ~/kubectlutil/kubectlutil.py --namespace hidenori --kubeconfig ~/.kube/config http -c info -n www-stellar-org-0`

This runs the command `info` for the node `www-stellar-org-0`

## Monitor

Example: `watch -n 10 python3 ~/kubectlutil/kubectlutil.py --namespace hidenori --kubeconfig ~/.kube/config monitor`

This prints helpful information when running a network simulation and updates it every 10 seconds.