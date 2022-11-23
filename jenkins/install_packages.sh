#!/bin/sh

# Installing ibmcloud cli
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh

ibmcloud plugin install container-service

# Installing oc cli
curl https://mirror.openshift.com/pub/openshift-v4/clients/oc/latest/linux/oc.tar.gz -o oc.tar.gz

tar xzf oc.tar.gz

mv oc /usr/local/bin/
mv kubectl /usr/local/bin/

yum install unzip -y

curl https://dl.google.com/go/go1.18.linux-amd64.tar.gz -o go1.18.linux-amd64.tar.gz

tar -C /usr/local -xzf go1.18.linux-amd64.tar.gz 

echo "export PATH=$PATH:/usr/local/go/bin" > /etc/environment

source /etc/environment
