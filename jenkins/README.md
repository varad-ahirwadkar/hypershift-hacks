
## Hypershift Jenkins Job

### Prerequisite:
- A VM with python3 installed.

### Steps to run:
1. Install required packages using install_packages.sh

	```./install_packages.sh```

2. Fill env.sh to edit various env var required to create a hypershift cluster, after edit, source it.

	```source env.sh```

3. Test procedure is programmed in python3, only standard libraries used, no need to install any other packages. All configurations will be picked up from env vars. Can directly run the script.

	```python3 run_e2e.py```
