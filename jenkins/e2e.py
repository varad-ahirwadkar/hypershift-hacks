import subprocess
import os
import json
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import base64
from pathlib import Path
import datetime
import time
import shutil

mgmtCluster = os.getenv("MANAGEMENT_CLUSTER")
apikey = os.getenv("IBMCLOUD_API_KEY")
region = os.getenv("REGION")
zone = os.getenv("ZONE")
vpcRegion = os.getenv("VPC_REGION")
resourceGroup = os.getenv("RESOURCE_GROUP")
baseDomain = os.getenv("BASEDOMAIN")
pullsecret = os.getenv("PULL_SECRET")
sshkey = os.getenv("SSH_KEY")
releaseImage = os.getenv("RELEASE_IMAGE")
nodePoolReplicas = os.getenv("NODEPOOL_REPLICAS")
sysType = os.getenv("SYS_TYPE")
procType = os.getenv("PROC_TYPE")
processors = os.getenv("PROCESSORS")
dumpDir = os.getenv("DUMP_DIR")

guestKubeconfigPath = "/tmp/ci-guest-kubeconfig"
mgmtClusterKubeconfigPath = "/tmp/ci-mgmt-kubeconfig"

def setupEnv():
    if apikey == "":
        raise Exception("IBMCLOUD_API_KEY is not set")

    api = "--apikey={}".format(apikey)
    subprocess.run(['ibmcloud', 'login', api,'-r', vpcRegion])

    f = os.open(mgmtClusterKubeconfigPath, os.O_RDWR|os.O_CREAT)

    subprocess.run(['ibmcloud', 'oc', 'cluster', 'config', '-c', mgmtCluster, '--admin', '--output', 'yaml'], stdout=f)

    os.close(f)

    os.environ["KUBECONFIG"] = mgmtClusterKubeconfigPath

    subprocess.run(["curl", "https://codeload.github.com/openshift/hypershift/zip/refs/heads/main", "-o", "hypershift.zip"])

    subprocess.run(["unzip", "-q", "-o", "hypershift.zip"])

    os.chdir("hypershift-main")

    out = subprocess.run(["make", "hypershift"])

def destroyCluster(name, infraID, vpcRegion, region, zone, resourceGroup, baseDomain):
    destroyClusterCmd = ["bin/hypershift", "destroy", "cluster", "powervs", 
    "--name", name, 
    "--infra-id", infraID, 
    "--vpc-region={}".format(vpcRegion), 
    "--region={}".format(region),
    "--zone={}".format(zone),
    "--resource-group={}".format(resourceGroup),
    "--base-domain={}".format(baseDomain)
    ]

    retry = 0
    while retry < 5:
        try:
            subprocess.run(["echo", "executing", " ".join(destroyClusterCmd)])
            out = subprocess.run(destroyClusterCmd)
            if out.check_returncode() is None:
                break
        except Exception as ex:
            subprocess.run(["echo", "caught", str(ex), "executing", " ".join(destroyClusterCmd)])

        retry += 1

def runE2e():

    # Installing hypershift operator ...
    subprocess.run(["bin/hypershift", "install"])

    name = "hypershift-ci-{}".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
    infraID = "{}-infra".format(name)

    createClusterCmd = ["bin/hypershift", 
    "create", 
    "cluster", 
    "powervs",
    "--name={}".format(name),
    "--infra-id={}".format(infraID),
    "--debug"]

    if pullsecret == None:
        raise Exception("PULL_SECRET is not set")
    else:
        createClusterCmd.append("--pull-secret={}".format(pullsecret))

    if baseDomain == None:
        raise Exception("BASEDOMAIN is not set")
    else:
        createClusterCmd.append("--base-domain={}".format(baseDomain))

    if releaseImage == None:
        raise Exception("RELEASE_IMAGE is not set")
    else:
        createClusterCmd.append("--release-image={}".format(releaseImage))

    if nodePoolReplicas == None:
        createClusterCmd.append("--node-pool-replicas=2")
    else:
        createClusterCmd.append("--node-pool-replicas={}".format(nodePoolReplicas))

    if resourceGroup == None:
        raise Exception("RESOURCE_GROUP is not set")
    else:
        createClusterCmd.append("--resource-group={}".format(resourceGroup))

    if region == None:
        raise Exception("REGION is not set")
    else:
        createClusterCmd.append("--region={}".format(region))
    
    if zone == None:
        raise Exception("ZONE is not set")
    else:
        createClusterCmd.append("--zone={}".format(zone))
    
    if vpcRegion == None:
        raise Exception("VPC_REGION is not set")
    else:
        createClusterCmd.append("--vpc-region={}".format(vpcRegion))

    if procType != None:
        createClusterCmd.append("--proc-type={}".format(procType))

    if processors != None:
        createClusterCmd.append("--processors={}".format(processors))

    if sysType != None:
        createClusterCmd.append("--sys-type={}".format(sysType))

    if sshkey != None:
        createClusterCmd.append("--ssh-key={}".format(sshkey))

    subprocess.run(["echo", "executing", " ".join(createClusterCmd)])

    createClusterFailed = False
    # Create guest cluster ...
    try:
        out = subprocess.run(createClusterCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["echo", out.stderr.decode()])
        if "Failed to create cluster" in out.stderr.decode():
            createClusterFailed = True
    except Exception as ex:
        subprocess.run(["echo", "caught", str(ex), "while executing 'bin/hypershift create cluster powervs' command"])
        createClusterFailed = True

    if createClusterFailed:
        destroyCluster(name, infraID, vpcRegion, region, zone, resourceGroup, baseDomain)
        raise Exception("cluster creation failed, see more on 'bin/hypershift create cluster powervs' command output from log")

    hostedClusterAvailableCmd = ["oc", "wait", "--timeout=10m", "--for=condition=Available", "--namespace=clusters", "hostedcluster/{}".format(name)]
    subprocess.run(["echo", "executing", " ".join(hostedClusterAvailableCmd)])
    subprocess.run(hostedClusterAvailableCmd)

    subprocess.run(["sleep", "15"])

    f = os.open(guestKubeconfigPath, os.O_RDWR|os.O_CREAT)

    subprocess.run(["bin/hypershift", "create", "kubeconfig", "--name={}".format(name)],stdout=f)

    os.close(f)

    os.environ["KUBECONFIG"] = guestKubeconfigPath
   
    clusterOperatorsReady = False
    waitConditionCmd = ["oc", "wait", "--timeout=1s", "clusterversion/version", "--for=condition=Available=True"]
    retry = 0
    while retry < 120:
        try:
            subprocess.run(["echo", "executing", " ".join(waitConditionCmd)])
            out = subprocess.run(waitConditionCmd)
            if out.check_returncode() is not None:
                subprocess.run(["echo", "Clusteroperators not yet ready"])
                subprocess.run(["oc", "get", "clusterversion/version"])
            else:
                subprocess.run(["echo", "Clusteroperators ready"])
                clusterOperatorsReady = True
                break
        except Exception as ex:
            subprocess.run(["echo", "caught", str(ex), "executing", " ".join(waitConditionCmd)])
        time.sleep(300)
        retry += 5

    os.environ["KUBECONFIG"] = mgmtClusterKubeconfigPath

    # Dump guest cluster ...
    dumpClusterCmd = ["bin/hypershift", "dump", "cluster", "--dump-guest-cluster", "--artifact-dir={}/{}-dump".format(dumpDir, name), "--name", name]
    try:
        subprocess.run(["echo", "executing", " ".join(dumpClusterCmd)])
        subprocess.run(dumpClusterCmd)
    except Exception as ex:
        subprocess.run(["echo", "caught", str(ex), "executing", " ".join(dumpClusterCmd)])

    # Destroy guest cluster ...
    destroyCluster(name, infraID, vpcRegion, region, zone, resourceGroup, baseDomain)

    if clusterOperatorsReady == False:
        raise Exception("cluster operators does not become available, see more on hosted cluster's dump.")

def cleanupEnv():
    # Delete namespaces
    try:
        subprocess.run(["oc", "delete", "namespace", "hypershift"])
        subprocess.run(["oc", "delete", "namespace", "clusters"])
    except Exception as ex:
        subprocess.run(["echo", "caught exception while deleting hypershift namespace", str(ex)])

    # Delete CRDs
    def unapplyCRD(dir):
        for filename in os.listdir(dir):
            subprocess.run(["oc", "delete", "-f", "{}/{}".format(dir, filename)])

    try:
        unapplyCRD("cmd/install/assets/cluster-api-provider-ibmcloud")
        unapplyCRD("cmd/install/assets/hypershift-operator")
    except Exception as ex:
        subprocess.run(["echo", "caught exception while deleting CRDs", str(ex)])

    # Delete hypershift operator image from workers
    try:
        nodesOut = subprocess.check_output(["oc", "get", "nodes", "-o", "json"])
        nodes = json.loads(nodesOut)
        for node in nodes['items']:
            subprocess.run(["oc", "debug", "node/{}".format(node["metadata"]["name"]), "--", "chroot", "/host", "crictl", "rmi", "-q"])
    except Exception as ex:
        subprocess.run(["echo", "caught exception while cleaning hypershift operator image in mgmt cluster's data nodes", str(ex)])

if __name__ == "__main__":
    try:
        setupEnv()
        runE2e()
    except Exception as ex:
        raise
    finally:
        cleanupEnv()
