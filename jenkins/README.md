
## Hypershift Jenkins Job

### Prerequisite:
- A VM with python3 installed.

## Authorization:

API Key used should have below services with respective roles for hypershift cluster to get created in IBM Cloud.

| Service                                                      | Roles                                                   |
|--------------------------------------------------------------|---------------------------------------------------------|
| Workspace for Power Systems Virtual Server - power-iaas      | Manager, Administrator                                  |
| VPC Infrastructure Services - is                             | Manager, Administrator                                  |
| Internet Services - internet-svcs                            | Manager, Administrator                                  |
| Direct Link - directlink                                     | Editor                                                  |
| IAM Identity Service - iam-identity                          | User API key creator, Service ID creator, Administrator |
| All account management services                              | Administrator                                           |
| All resources in account                                     | Manager, Editor                                         |

To run this jenkins job, need another Service access as well to access the management ROKS cluster to create manifests of hypershift test cluster.

| Service                                                      | Roles                   |
|--------------------------------------------------------------|-------------------------|
| Kubernetes Service - containers-kubernetes                   | Manager, Administrator  |

### Steps to run:
1. Install required packages using install_packages.sh

	```./install_packages.sh```

2. Fill env.sh to edit various env var required to create a hypershift cluster, after edit, source it.

	```source env.sh```

3. Test procedure is programmed in python3, only standard libraries used, no need to install any other packages. All configurations will be picked up from env vars. Can directly run the script.

	```python3 run_e2e.py```
