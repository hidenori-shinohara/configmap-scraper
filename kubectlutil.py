import argparse
import toml
from kubernetes import client, config

PREFERRED_PEERS = "PREFERRED_PEERS"
QUORUM_SET = "QUORUM_SET"

def getPodList(args):
    config.load_kube_config()

    v1 = client.CoreV1Api()
    a = v1.list_namespaced_config_map(args.namespace)
    return v1.list_namespaced_pod(args.namespace)

def getConfigMapList(args):
    config.load_kube_config()

    v1 = client.CoreV1Api()
    return v1.list_namespaced_config_map(args.namespace)


def getip2podname():
    ip2podname = dict()
    for item in ret.items:
        ip2podname[item.status.pod_ip] = item.metadata.name
    return ip2podname

def podname2name(podname, args):
    return podname[21:-(49 + len(args.namespace))]

def cleanPreferredPeers(preferredPeers, args):
    for i in range(len(preferredPeers)):
        preferredPeers[i] = podname2name(preferredPeers[i], args)
    preferredPeers.sort()

def cleanQuorumSet(quroumSet):
    # TODO
    return

def configmap(args):
    name = args.node if args.node else "www-stellar-org-0"
    configMapList = getConfigMapList(args)
    for configMap in configMapList.items:
        if name in configMap.metadata.name:
            parsed_toml = toml.loads(configMap.data['stellar-core.cfg'])
            if not args.raw:
                cleanPreferredPeers(parsed_toml[PREFERRED_PEERS], args)
                cleanQuorumSet(parsed_toml[QUORUM_SET])
            print(toml.dumps(parsed_toml))

def addConfigmapParser(subparsers):
    parser_configmap = subparsers.add_parser("configmap",
                                           help="Get the configmap")
    parser_configmap.add_argument("-n",
          "--node",
          required=False,
          help="Optional flag to specify the node. If none, www-stellar-org-0 will be used.")

    parser_configmap.add_argument("-r",
          "--raw",
          action='store_true',
          help="Optional flag to output the raw configmap. If not set, it simplifies the output")

    parser_configmap.set_defaults(func=configmap)


def main():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("-ns",
                                 "--namespace",
                                 help="namespace")

    subparsers = argument_parser.add_subparsers()
    addConfigmapParser(subparsers)

    args = argument_parser.parse_args()                              
    args.func(args)


if __name__ == '__main__':
    main()
