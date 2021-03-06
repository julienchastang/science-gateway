FROM centos:7

###
# Update the system. Install stuff.
###

ADD kubectl.repo /tmp/

RUN cat /tmp/kubectl.repo >> /etc/yum.repos.d/kubernetes.repo && \
    rm /tmp/kubectl.repo

RUN yum update yum -y

RUN yum install -y vim telnet openssh openssh-clients git vi less nano wget \
    unzip kubectl

RUN yum install -y http://rdo.fedorapeople.org/rdo-release.rpm

RUN yum install -y python-glanceclient python-openstackclient

###
# pip
###

RUN yum -y install epel-release python-pip

###
# Terraform
###

ENV TERRAFORM_VERSION=0.11.8

RUN  wget https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    unzip terraform_${TERRAFORM_VERSION}_linux_amd64.zip -d /usr/local/bin/

###
# Set up openstack account and create bin directory
###

RUN useradd -ms /bin/bash openstack

ENV HOME /home/openstack

RUN mkdir -p $HOME/bin

ENV PATH=$HOME/bin:$PATH

###
# Clone kubespray
###

RUN git clone https://github.com/zonca/jetstream_kubespray \
    $HOME/jetstream_kubespray

RUN pip install --upgrade pip

RUN pip install -r $HOME/jetstream_kubespray/requirements.txt

RUN mkdir $HOME/.kube


###
# Add various utilities
###

ADD bin/boot.sh bin/mount.sh bin/secgroup.sh bin/teardown.sh \
   bin/unidata-secgroups.sh bin/wrangler-jetstream.sh bin/wrangler-secgroup.sh \
   bin/swap-vm.sh bin/kube-setup.sh bin/swap-vm.sh bin/kube-setup2.sh $HOME/bin/

RUN chmod +x $HOME/bin/*.sh

ADD .bashrc $HOME/

###
# Finalize
###

RUN chown -R openstack:openstack $HOME/

WORKDIR $HOME

USER openstack
