import argparse
import random
import re
import toml
import ipaddress
import subprocess
import datetime
import json
import multiprocessing
from kubernetes.client.rest import ApiException
from kubernetes import client, config
import kubernetes.client

PREFERRED_PEERS = "PREFERRED_PEERS"
QUORUM_SET = "QUORUM_SET"


def getCoreV1Api(args):
    config.load_kube_config(config_file=args.kubeconfig)
    return client.CoreV1Api()


def getPodList(args):
    v1 = getCoreV1Api(args)
    api_instance = kubernetes.client.ExtensionsV1beta1Api()
    ingress = api_instance.list_namespaced_ingress(args.namespace)
    print(ingress)
    return v1.list_namespaced_pod(args.namespace)


def getConfigMapList(args):
    v1 = getCoreV1Api(args)
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
    template = 'curl {}.stellar-supercluster.kube001.' \
               'services.stellar-ops.com/{}/core/{}'
    return template.format(podName[:16], podName, cmd)


def httpCommand(args):
    podName = getPodName(args)
    process = subprocess.Popen(getCurlCommand(podName, args.command).split())
    process.communicate()


def printPodNamesAndStatuses(podNamesPerStatus):
    maxLength = 0
    for status in podNamesPerStatus:
        maxLength = max(maxLength, len(status))
    for status in sorted(podNamesPerStatus):
        podNameList = podNamesPerStatus[status]
        random.shuffle(podNameList)
        maxNumberToPrint = 5
        podNamesToPrint = list(map(lambda longName: longName[21:],
                                   podNameList[:min(maxNumberToPrint,
                                                    len(podNameList))]))
        podNamesToPrint.sort()
        dotsOrNoDots = "..." if len(podNameList) > maxNumberToPrint else ""
        template = "{:<" + str(maxLength) + "} => {:>3} pods: {}"
        print(template.format(status,
                              len(podNameList),
                              ", ".join(podNamesToPrint) +
                              dotsOrNoDots))

def formatTimeDiff(td):
    # The default format is HH:MM:SS.SSSS
    # This code turns that into HH:MM:SS since
    # we don't need to be that precise.
    return str(td).split('.', 1)[0]


def printPodStatuses(podList):
    podNamesPerStatus = dict()
    durations = []
    for pod in podList.items:
        status = pod.status.phase
        if status not in podNamesPerStatus:
            podNamesPerStatus[status] = []
        podNamesPerStatus[status].append(pod.metadata.name)
        now = datetime.datetime.now().astimezone(pod.status.start_time.tzinfo)
        durations.append(now - pod.status.start_time)
    durations.sort()
    if len(durations) > 0:
        print("youngest = {}".format(formatTimeDiff(durations[0])))
        print("median   = {}".format(formatTimeDiff(durations[len(durations) // 2])))
        print("oldest   = {}".format(formatTimeDiff(durations[-1])))
        print()
    printPodNamesAndStatuses(podNamesPerStatus)


def printSCPStatuses(podList):
    manager = multiprocessing.Manager()
    podNamesPerSCPStatus = manager.dict()
    podNamesPerLedger = manager.dict()

    def getSCPStatus(podName):
        try:
            cmd = getCurlCommand(podName, "info")
            output = subprocess.run(cmd.split(), capture_output=True).stdout
            status = json.loads(output)["info"]["state"]
            ledgerInfo = json.loads(output)["info"]["ledger"]
            ledger = "Ledger {:>3}({})".format(ledgerInfo["num"],
                                            ledgerInfo["hash"][:5])
        except Exception as e:
            status = ledger = "Unknown: {}".format(e)
        if status not in podNamesPerSCPStatus:
            podNamesPerSCPStatus[status] = manager.list()
        if ledger not in podNamesPerLedger:
            podNamesPerLedger[ledger] = manager.list()
        podNamesPerSCPStatus[status].append(podName)
        podNamesPerLedger[ledger].append(podName)

    processes = []
    for pod in podList.items:
        podName = pod.metadata.name
        process = multiprocessing.Process(target=getSCPStatus,
                                          args=(podName,))
        processes.append(process)
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    printPodNamesAndStatuses(podNamesPerSCPStatus)
    print()
    printPodNamesAndStatuses(podNamesPerLedger)


def printPeerConnectionStatuses(podList, args):
    configMapList = getConfigMapList(args)
    targetConnectionCount = dict()
    for pod in podList.items:
        podName = pod.metadata.name
        for configMap in configMapList.items:
            if podName in configMap.metadata.name:
                parsedToml = toml.loads(configMap.data['stellar-core.cfg'])
                targetConnectionCount[configMap.metadata.name] = len(parsedToml[PREFERRED_PEERS])

    manager = multiprocessing.Manager()
    currentConnectionCount = manager.dict()

    def getConnectionCount(podName):
        try:
            cmd = getCurlCommand(podName, "peers")
            results = json.loads(subprocess.run(cmd.split(),
                                                capture_output=True).stdout)
            n = len((results["authenticated_peers"]["inbound"] or []) +
                    (results["authenticated_peers"]["outbound"] or []))
        except Exception as e:
            n = 0
        currentConnectionCount[podName] = n

    processes = []
    for pod in podList.items:
        podName = pod.metadata.name
        process = multiprocessing.Process(target=getConnectionCount,
                                          args=(podName,))
        processes.append(process)
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    percentageAndPodNames = dict()
    for name in currentConnectionCount:
        targetCount = 1000000
        for podName in targetConnectionCount:
            if name in podName:
                targetCount = targetConnectionCount[podName]
        currentCount = currentConnectionCount[name]
        percentage = "{:>3}%".format(((10 * currentCount) // targetCount) * 10)
        if percentage not in percentageAndPodNames:
            percentageAndPodNames[percentage] = []
        percentageAndPodNames[percentage].append(name)
    printPodNamesAndStatuses(percentageAndPodNames)


def monitor(args):

    podList = getPodList(args)
    print("{} pods total".format(len(podList.items)))
    print()
    print("#Pod Status#")
    print()
    printPodStatuses(podList)
    print()
    print("#SCP Status#")
    print()
    printSCPStatuses(podList)
    print()
    print("#Peer Connection Status#")
    print()
    printPeerConnectionStatuses(podList, args)


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
    ls = (content["authenticated_peers"]["inbound"] or []) + \
         (content["authenticated_peers"]["outbound"] or [])
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
                        help="Optional flag to specify the node."
                             "If none, www-stellar-org-0 will be used.")


def addRaw(parser):
    parser.add_argument("-r",
                        "--raw",
                        action='store_true',
                        help="Optional flag to output"
                             "with as little modification as possible")


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
                                   help="HTTP command to run."
                                        "If not set, it runs info")
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
                                 default="",
                                 help="namespace")
    argument_parser.add_argument("-kc",
                                 "--kubeconfig",
                                 default="~/.kube/config",
                                 help="Kubernetes config file")

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
