import argparse
import random
import re
import toml
import ipaddress
import subprocess
import json
from kubernetes.client.rest import ApiException
from kubernetes import client, config

PREFERRED_PEERS = "PREFERRED_PEERS"
QUORUM_SET = "QUORUM_SET"


def getCoreV1Api():
    config.load_kube_config()
    return client.CoreV1Api()


def getPodList(args):
    v1 = getCoreV1Api()
    return v1.list_namespaced_pod(args.namespace)


def getConfigMapList(args):
    v1 = getCoreV1Api()
    return v1.list_namespaced_config_map(args.namespace)


def getip2podname(args):
    ip2podname = dict()
    podList = getPodList(args)
    for item in podList.items:
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
    configMapList = getConfigMapList(args)
    for configMap in configMapList.items:
        if args.node in configMap.metadata.name:
            result = configMap.data['stellar-core.cfg']
            if not args.raw:
                parsedToml = toml.loads(result)
                cleanPreferredPeers(parsedToml[PREFERRED_PEERS], args)
                cleanQuorumSet(parsedToml[QUORUM_SET])
                result = json.dumps(parsedToml, sort_keys=True, indent=4)
            print(result)


def getPodName(args):
    podList = getPodList(args)
    for pod in podList.items:
        podName = pod.metadata.name
        if args.node in podName:
            return podName
    return "not found"


def getCurlCommand(podName, cmd):
    # TODO: Find out a way to get ingress from the API.
    template = 'curl {}.stellar-supercluster.kube001.services.stellar-ops.com/{}/core/{}'
    return template.format(podName[:16], podName, cmd)


def httpCommand(args):
    podName = getPodName(args)
    process = subprocess.Popen(getCurlCommand(podName, args.command).split())
    process.communicate()


def printPodNamesAndStatuses(podList):
    podNamesPerStatus = dict()
    totalCount = 0
    for pod in podList.items:
        totalCount += 1
        status = pod.status.phase
        name = pod.metadata.name
        if status not in podNamesPerStatus:
            podNamesPerStatus[status] = []
        podNamesPerStatus[status].append(name)
    print("{} pods total".format(totalCount))
    for status in podNamesPerStatus:
        examplePodNames = ""
        podNameList = podNamesPerStatus[status]
        random.shuffle(podNameList)
        maxNumberToPrint = 5
        podNamesToPrint = list(map(lambda longName: longName[21:],
                                   podNameList[:min(maxNumberToPrint,
                                                    len(podNameList))]))
        podNamesToPrint.sort()
        print("{} => {} pods: {}".format(status,
                                         len(podNameList),
                                         ", ".join(podNamesToPrint) +
                                         ("..." if len(podNameList) > maxNumberToPrint
                                          else "")))


def monitor(args):
    podList = getPodList(args)
    printPodNamesAndStatuses(podList)


def logs(args):
    try:
        v1 = getCoreV1Api()
        apiResponse = v1.read_namespaced_pod_log(name=getPodName(args),
                                                 namespace=args.namespace,
                                                 container="stellar-core-run")
        print(apiResponse)
    except ApiException as e:
        print('Found exception in reading the logs')
        print(e)


def peers(args):
    podName = getPodName(args)
    cmd = getCurlCommand(podName, "peers")
    print("Running {}".format(cmd))
    results = subprocess.run(cmd.split(), stdout=subprocess.PIPE)
    content = json.loads(results.stdout)
    ls = content["authenticated_peers"]["inbound"] + \
        content["authenticated_peers"]["outbound"]
    ip2podname = getip2podname(args)
    listOfPeers = []
    for node in ls:
        ipWithPort = node["address"]
        ip = re.match(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', ipWithPort)[0]
        podname = ip2podname[ip]
        if not args.raw:
            podname = podname[21:]
        listOfPeers.append(podname)
    listOfPeers.sort()
    for peer in listOfPeers:
        print(peer)
    return


def addNodeArgument(parser):
    parser.add_argument("-n",
                        "--node",
                        default="www-stellar-org-0",
                        help="Optional flag to specify the node. If none, www-stellar-org-0 will be used.")


def addRaw(parser):
    parser.add_argument("-r",
                        "--raw",
                        action='store_true',
                        help="Optional flag to output with as little modification as possible")


def addConfigmapParser(subparsers):
    parserConfigMap = subparsers.add_parser("configmap",
                                            help="Get the configmap")
    addNodeArgument(parserConfigMap)
    addRaw(parserConfigMap)
    parserConfigMap.set_defaults(func=configmap)


def addHttpCommandParser(subparsers):
    parserHttpCommand = subparsers.add_parser("http",
                                              help="Run http command")
    addNodeArgument(parserHttpCommand)
    parserHttpCommand.add_argument("-c",
                                   "--command",
                                   default="info",
                                   help="HTTP command to run. If not set, it runs info")
    parserHttpCommand.set_defaults(func=httpCommand)


def addMonitorParser(subparsers):
    parserMonitor = subparsers.add_parser("monitor",
                                          help="Run the monitoring mode")
    addNodeArgument(parserMonitor)
    parserMonitor.set_defaults(func=monitor)


def addLogsParser(subparsers):
    parserLogs = subparsers.add_parser("logs", help="Get the logs")
    addNodeArgument(parserLogs)
    parserLogs.set_defaults(func=logs)


def addPeersParser(subparsers):
    parserPeers = subparsers.add_parser("peers", help="List all the peers")
    addNodeArgument(parserPeers)
    addRaw(parserPeers)
    parserPeers.set_defaults(func=peers)


def main():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("-ns",
                                 "--namespace",
                                 default="hidenori",
                                 help="namespace")

    subparsers = argument_parser.add_subparsers()
    addConfigmapParser(subparsers)
    addHttpCommandParser(subparsers)
    addMonitorParser(subparsers)
    addLogsParser(subparsers)
    addPeersParser(subparsers)

    args = argument_parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
