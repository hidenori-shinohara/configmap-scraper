# kubectlutil

A script to make it easy to monitor supercluster jobs.

## Configmap
Example: `python3 ~/kubectlutil/kubectlutil.py --namespace hidenori --kubeconfig ~/.kube/config configmap -n satoshipay-io-1`

This prints the readable, formatted configmap for the node `satoshipay-io-1`.

## HTTP endpoint
Example: `python3 ~/kubectlutil/kubectlutil.py --namespace hidenori --kubeconfig ~/.kube/config http -c info -n www-stellar-org-0`

This runs the command `info` for the node `www-stellar-org-0`

## Monitor

Examples:
- `watch -n 10 python3 ~/kubectlutil/kubectlutil.py --namespace hidenori --kubeconfig ~/.kube/config monitor`
- `watch -n 10 python3 ~/kubectlutil/kubectlutil.py --namespace default --kubeconfig /etc/rancher/k3s/k3s.yaml monitor`

This prints helpful information when running a network simulation and updates it every 10 seconds.

## Other features

- It also supports `logs` and `peers`.
- This also works with k3s by passing the appropriate namespace (likely `default`) and kubeconfig (likely `/etc/rancher/k3s/k3s.yaml`)