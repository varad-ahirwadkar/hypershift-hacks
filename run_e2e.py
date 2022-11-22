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

def setupEnv():
    if apikey == "":
        raise Exception("IBMCLOUD_API_KEY is not set")

    api = "--apikey={}".format(apikey)
    subprocess.run(['ibmcloud', 'login', api,'-r', vpcRegion])

    output = subprocess.check_output(['ibmcloud', 'oc', 'cluster', 'get', '-c', mgmtCluster, '--output', 'json'])
    clusterInfo = json.loads(output)
    masterURL = clusterInfo["masterURL"]

    issuerURL = "{}/.well-known/oauth-authorization-server".format(masterURL)
    with urlopen(issuerURL) as response:
        body = response.read()

    issuerURL = json.loads(body)['issuer']

    tokenURL = "{}/oauth/authorize?client_id=openshift-challenging-client&response_type=token".format(issuerURL)


    r = Request(tokenURL)
    r.add_header("X-CSRF-Token", "a")
    api = '%s:%s' % ("apikey", apikey)
    apibytes = api.encode("ascii")
    apiencoded = base64.b64encode(apibytes)
    r.add_header("Authorization", "Basic %s" % apiencoded.decode('utf-8'))
    res = urlopen(r)

    parsed = urlparse(res.url)
    frag = parsed.fragment
    access_token = ""
    for param in frag.split("&"):
        if "access_token" in param:
            paramSplit = param.split("=")
            access_token = paramSplit[1]

    try:
        shutil.rmtree("{}/.kube".format(Path.home()))
    except:
        pass

    subprocess.run(["oc", "login", "--token", access_token,"--server", masterURL])

    subprocess.run(["curl", "https://codeload.github.com/openshift/hypershift/zip/refs/heads/main", "-o", "hypershift.zip"])

    subprocess.run(["unzip", "-q", "-o", "hypershift.zip"])

    os.chdir("hypershift-main")

    out = subprocess.run(["make"])

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
    # Creating guest cluster ...
    subprocess.run(createClusterCmd)

    retry = 0
    while retry < 2:
        try:
            hostedClusterAvailableCmd = ["oc", "wait", "--timeout=10m", "--for=condition=Available", "--namespace=clusters", "hostedcluster/{}".format(name)]
            subprocess.run(["echo", "executing", " ".join(hostedClusterAvailableCmd)])
            out = subprocess.run(hostedClusterAvailableCmd)
            if out.check_returncode() is None:
                break
        except Exception:
            pass
        retry += 1


    subprocess.run(["sleep", "15"])

    kubeconfigPath = "{}/{}-kubeconfig".format(os.getcwd(), name)
    f = os.open(kubeconfigPath, os.O_RDWR|os.O_CREAT)

    subprocess.run(["bin/hypershift", "create", "kubeconfig", "--name={}".format(name)],stdout=f)

    os.close(f)

    os.environ["KUBECONFIG"] = kubeconfigPath
   
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
                break
        except Exception as ex:
            subprocess.run(["echo", "caught", str(ex), "executing", " ".join(waitConditionCmd)])
        time.sleep(300)
        retry += 5

    os.unsetenv("KUBECONFIG")

    os.remove(kubeconfigPath)

    dumpClusterCmd = ["bin/hypershift", "dump", "cluster", "--dump-guest-cluster", "--artifact-dir={}/{}-dump".format(dumpDir, name), "--name", name]
    try:
        subprocess.run(["echo", "executing", " ".join(dumpClusterCmd)])
        subprocess.run(dumpClusterCmd)
    except Exception as ex:
        subprocess.run(["echo", "caught", str(ex), "executing", " ".join(dumpClusterCmd)])

    # Destroying guest cluster ....

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
    while retry < 10:
        try:
            subprocess.run(["echo", "executing", " ".join(destroyClusterCmd)])
            out = subprocess.run(destroyClusterCmd)
            if out.check_returncode() is None:
                break
        except Exception as ex:
            subprocess.run(["echo", "caught", str(ex), "executing", " ".join(destroyClusterCmd)])

        retry += 1

def cleanupEnv():
    try:
        subprocess.run(["oc", "delete", "namespace", "hypershift"])
    except Exception as ex:
        subprocess.run(["echo", "caught exception while deleting hypershift namespace", str(ex)])

    def unapplyCRD(dir):
        for filename in os.listdir(dir):
            subprocess.run(["oc", "delete", "-f", "{}/{}".format(dir, filename)])

    try:
        unapplyCRD("cmd/install/assets/cluster-api-provider-ibmcloud")
        unapplyCRD("cmd/install/assets/hypershift-operator")
    except Exception as ex:
        subprocess.run(["echo", "caught exception while deleting CRDs", str(ex)])

    try:
        nodesOut = subprocess.check_output(["oc", "get", "nodes", "-o", "json"])
        nodes = json.loads(nodesOut)
        for node in nodes['items']:
            subprocess.run(["oc", "debug", "node/{}".format(node["metadata"]["name"]), "--", "chroot", "/host", "crictl", "rmi", "-q"])
    except Exception as ex:
        subprocess.run(["echo", "caught exception while cleaning hypershift operator image in mgmt cluster's data nodes", str(ex)])

    os.chdir("../")
    subprocess.run(["pwd"])

    shutil.rmtree("hypershift-main")
    os.remove("hypershift.zip")

if __name__ == "__main__":
    try:
        setupEnv()
        runE2e()
    except Exception as ex:
        print("caught", ex)
    finally:
        cleanupEnv()