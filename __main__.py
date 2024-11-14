import pulumi
import pulumi_aws as aws
from pulumi_command import local
import ipaddress

class SecurityGroup:
   def __init__(self, name, vpc_id="", description="", ingresses=[], egresses=[], parent=None, aws_provider=None):
       self.name = name
       self.vpc_id = vpc_id
       self.description = description
       self.ingresses = ingresses
       self.egresses = egresses
       self.parent = parent
       self.aws_provider = aws_provider
       self.create_sg()

   def create_sg(self):
       self.sg = aws.ec2.SecurityGroup(
           f"sg-{self.name}",
           vpc_id=self.vpc_id,
           name=self.name,
           description=self.description,
           opts=pulumi.ResourceOptions(parent=self.parent, provider=self.aws_provider),
       )

       self.create_egresses()
       self.create_ingresses()

   def create_egresses(self):
       if len(self.egresses) == 0:
           egress = aws.vpc.SecurityGroupEgressRule(
               f"sg-egress-{self.name}", security_group_id=self.sg.id, ip_protocol="-1", cidr_ipv4="0.0.0.0/0", opts=pulumi.ResourceOptions(parent=self.sg, provider=self.aws_provider)
           )
       else:
           pass #TODO

   def create_ingresses(self):
       for i, ing in enumerate(self.ingresses):
           source_sg_id = ing.get("source_security_group_id")
           if source_sg_id == "self":
               source_sg_id = self.sg.id
           ingress = aws.vpc.SecurityGroupIngressRule(
               f"sg-ingress-{self.name}-{i}",
               security_group_id=self.sg.id,
               ip_protocol=ing["ip_protocol"],
               cidr_ipv4=ing.get("cidr_ip"),
               from_port=ing["from_port"],
               to_port=ing["to_port"],
               referenced_security_group_id=source_sg_id,
               opts=pulumi.ResourceOptions(parent=self.sg, provider=self.aws_provider),
           )

   def get_id(self):
       return self.sg.id

class VPC:
   def __init__(self, name, cidr="10.0.0.0/16", azs=[], parent=None, aws_provider=None):
       self.name = name
       self.cidr = cidr
       self.parent = parent
       self.aws_provider = aws_provider
       self.create_vpc()
       new_prefix = int(cidr.split("/")[1])+2
       self.azs = azs
       self.subnet_cidr = list(ipaddress.ip_network(cidr).subnets(new_prefix=new_prefix))

   def create_vpc(self):
       tags = {
         "Name": self.name
       }
       self.vpc = aws.ec2.Vpc(
           f"vpc-{self.name}",
           cidr_block=self.cidr,
           enable_dns_hostnames=True,
           enable_dns_support=True,
           opts=pulumi.ResourceOptions(parent=self.parent, provider=self.aws_provider),
           tags=tags
       )

   def get_vpc_id(self):
       return self.vpc.id

   def get_subnet_ids(self):
       return [self.subnets["subnet-public-0"].id, self.subnets["subnet-public-1"].id]

   def create_subnets(self):
       subnets_map = {
         f"subnet-public-0": 0,
         f"subnet-public-1": 1,
       }
       self.subnets = {}

       for name, index in subnets_map.items():
           self.subnets[name] = aws.ec2.Subnet(
               name + f"-{self.name}",
               vpc_id=self.vpc.id,
               cidr_block=self.subnet_cidr[index].with_prefixlen,
               availability_zone=self.azs[index % 2],
               opts=pulumi.ResourceOptions(parent=self.vpc, provider=self.aws_provider),
               map_public_ip_on_launch=(name.startswith("subnet-public-")),
               tags={"Name": name + f"-{self.name}"},
           )
   def create_route_table(self, table_type):
       tags = {
         "Name": f"vpc-rt-{table_type}-{self.name}",
       }

       rt = aws.ec2.RouteTable(f"vpc-rt-{table_type}-{self.name}",
                                        vpc_id=self.vpc.id,
                                        opts=pulumi.ResourceOptions(parent=self.vpc, provider=self.aws_provider),
                                        tags=tags,
                )

       aws.ec2.Route(f"vpc-rt-r-{table_type}-{self.name}",
                                 route_table_id=rt.id,
                                 destination_cidr_block="0.0.0.0/0",
                                 gateway_id=self.igw.id,
                                 opts=pulumi.ResourceOptions(parent=rt, provider=self.aws_provider)
       )

       aws.ec2.RouteTableAssociation(f"vpc-rt-assoc-{table_type}-{self.name}-1",
                                        subnet_id=self.subnets[f"subnet-{table_type}-0"],
                                        route_table_id=rt.id,
                                        opts=pulumi.ResourceOptions(parent=rt, provider=self.aws_provider)
       )

       aws.ec2.RouteTableAssociation(f"vpc-rt-assoc-{table_type}-{self.name}-2",
                                        subnet_id=self.subnets[f"subnet-{table_type}-1"],
                                        route_table_id=rt.id,
                                        opts=pulumi.ResourceOptions(parent=rt, provider=self.aws_provider)
       )

   def create_internet_gateway(self):
       self.igw = aws.ec2.InternetGateway(f"vpc-igw-{self.name}",
                                                vpc_id=self.vpc.id,
                                                opts=pulumi.ResourceOptions(parent=self.parent, provider=self.aws_provider))
   def create_ec2(self, profile, sg_id, ami_id, key_name, user_data):
       self.ec2 = aws.ec2.Instance(f"ec2-{region}",
                                     instance_type="t3.medium",
                                     subnet_id=self.get_subnet_ids()[0],
                                     root_block_device={"volume_size": 50},
                                     key_name=key_name,
                                     ami=ami_id,
                                     iam_instance_profile=profile,
                                     vpc_security_group_ids=[sg_id],
                                     user_data=user_data,
                                     opts=pulumi.ResourceOptions(parent=self.parent, provider=self.aws_provider),
                                    )

def get_ami_id(aws_provider):
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["amazon"],
        filters=[
            {
                "name": "architecture",
                "values": ["x86_64"],
            },
            {
                "name": "name",
                "values": ["al2023-ami-2023*"],
            },
        ],
        opts=pulumi.InvokeOptions(provider=aws_provider)
        )
    return ami.id

def get_vpc_id(aws_provider):
    vpc = aws.ec2.get_vpc(
          default=True,
          opts=pulumi.InvokeOptions(provider=aws_provider),
          )
    return vpc.id

def create_iam_role():
    instance_assume_role_policy = aws.iam.get_policy_document(statements=[{
        "actions": ["sts:AssumeRole"],
        "principals": [{
            "type": "Service",
            "identifiers": ["ec2.amazonaws.com"],
        }],
    }],
    )
    role = aws.iam.Role(f"instance",
        name="admin-role-multiaccount",
        assume_role_policy=instance_assume_role_policy.json,
        )

    aws.iam.RolePolicyAttachment(f"test-attach",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AdministratorAccess",
    )

    aws.iam.InstanceProfile(f"test_profile",
        name="test_profile",
        role=role.name)

    return "test_profile"

def create_key_pair(parent, region, aws_provider):
    deployer = aws.ec2.KeyPair(f"deployer-multiaccount-{region}",
        key_name="deployer-multiaccount",
        public_key=public_key,
        opts=pulumi.ResourceOptions(parent=parent, provider=aws_provider),
        )
    return "deployer-multiaccount"

def create_s3_bucket(region):
    aws_provider = aws.Provider(f"aws-s3-{region}", region=region)
    return aws.s3.BucketV2("s3-bucket-pulumi-state",
        bucket_prefix="littlejo-cmesh",
        tags={
            "Name": "My bucket",
            "Environment": "Dev",
        },
        opts=pulumi.ResourceOptions(provider=aws_provider),
        )

def get_userdata(s3_bucket, s3_region, ec2_region):
    combined = pulumi.Output.all(s3_bucket, s3_region, ec2_region)
    return combined.apply(lambda vars: f"""#!/bin/bash
yum install yum-utils shadow-utils make git -y

git clone https://github.com/littlejo/pulumi-cilium-python-examples /root/pulumi-cilium-python-examples

curl -fsSL https://get.pulumi.com | sh
echo 'export PATH=$PATH:/.pulumi/bin' >> /root/.bashrc
echo 'export BUCKET_S3=s3://{vars[0]}?region={vars[1]}' >> /root/.bashrc
echo 'export AWS_DEFAULT_REGION={vars[2]}' >> /root/.bashrc
echo 'export PULUMI_CONFIG_PASSPHRASE=""' >> /root/.bashrc

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)
CLI_ARCH=amd64
curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/$CILIUM_CLI_VERSION/cilium-linux-$CLI_ARCH.tar.gz
tar xzvfC cilium-linux-$CLI_ARCH.tar.gz /usr/local/bin

TERRATEST_VERSION=0.0.8
wget https://github.com/littlejo/check-cilium-clustermesh/releases/download/v$TERRATEST_VERSION/cilium-clustermesh-terratest-$TERRATEST_VERSION-linux-amd64.tar.gz
tar xzvfC cilium-clustermesh-terratest-$TERRATEST_VERSION-linux-amd64.tar.gz /usr/local/bin

yum-config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
yum install gh -y

git clone https://github.com/littlejo/results-cilium-clustermesh /root/results-cilium-clustermesh

git clone https://github.com/littlejo/check-cilium-clustermesh
cp check-cilium-clustermesh/scripts/*.py /usr/local/bin
cp check-cilium-clustermesh/scripts/*.sh /usr/local/bin
chmod 755 /usr/local/bin/cilium-status.py /usr/local/bin/cilium-clustermesh-status.py /usr/local/bin/check-cilium.sh

curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
""")

def get_config_value(key, default=None, value_type=str):
    try:
        value = config.require(key)
        return value_type(value)
    except pulumi.ConfigMissingError:
        return default
    except ValueError:
        print(f"Warning: Could not convert config '{key}' to {value_type.__name__}, using default.")
        return default

config = pulumi.Config()

regions = get_config_value("awsRegions", "us-east-1,us-east-1").split(",")
bucket_region = get_config_value("s3Region", "us-east-1")
public_key = get_config_value("publicKey", "TODO")

profile = create_iam_role()
bucket = create_s3_bucket(bucket_region)

for region in regions:
    null = local.Command(f"{region}-vpc")
    aws_provider = aws.Provider(f"aws-{region}", region=region, opts=pulumi.ResourceOptions(parent=null))
    key_pair = create_key_pair(null, region, aws_provider)
    azs_info = aws.get_availability_zones(state="available", opts=pulumi.InvokeOptions(provider=aws_provider, parent=null))
    azs = azs_info.names[:2]
    vpc = VPC(f"public-{region}", azs=azs, aws_provider=aws_provider, parent=null)
    vpc.create_subnets()
    vpc.create_internet_gateway()
    vpc.create_route_table("public")
    sg = SecurityGroup(f"ec2-{region}", vpc_id=vpc.get_vpc_id(), description="Allow ssh inbound traffic", ingresses=[{"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 22, "to_port": 22}], parent=null, aws_provider=aws_provider)
    user_data = get_userdata(bucket.id, bucket_region, region)
    vpc.create_ec2(profile, sg.sg, get_ami_id(aws_provider), key_pair, user_data)
    pulumi.export(f"ip_{region}", vpc.ec2.public_ip)
    pulumi.export(f"bucket_id_{region}", bucket.id)
    #pulumi.export(f"user_data_{region}", user_data)
    #pulumi.export(f"vpc_id_{region}", get_vpc_id(aws_provider))

