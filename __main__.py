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
       return [self.subnets["subnet-private-0"].id, self.subnets["subnet-private-1"].id]

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

   def create_internet_gateway(self):
       self.igw = aws.ec2.InternetGateway(f"vpc-igw-{self.name}",
                                                vpc_id=self.vpc.id,
                                                opts=pulumi.ResourceOptions(parent=self.parent, provider=self.aws_provider))

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
        name="admin-role",
        assume_role_policy=instance_assume_role_policy.json,
        )

    aws.iam.RolePolicyAttachment(f"test-attach",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AdministratorAccess",
    )

    aws.iam.InstanceProfile(f"test_profile",
        name="test_profile",
        role=role.name)

def create_key_pair():
    deployer = aws.ec2.KeyPair("deployer",
        key_name="deployer-key",
        public_key="aaaa",
        )

def create_s3_bucket(region):
    aws_provider = aws.Provider(f"aws-s3-{region}", region=region)
    example = aws.s3.BucketV2("s3-bucket-pulumi-state",
        bucket="littlejo-cmesh",
        tags={
            "Name": "My bucket",
            "Environment": "Dev",
        })

regions = [
           "us-east-1",
           "us-west-2",
           #"ca-central-1",
           #"sa-east-1",
           #"eu-west-3",
           #"eu-west-1",
           #"eu-north-1",
           #"ap-northeast-1",
           #"ap-southeast-2",
           #"af-south-1",
           #"me-south-1",
          ]
#regions = ["us-east-1", "us-west-2"]
regions = ["us-east-1"]

for region in regions:
    null = local.Command(f"{region}-vpc")
    aws_provider = aws.Provider(f"aws-{region}", region=region, opts=pulumi.ResourceOptions(parent=null))
    azs_info = aws.get_availability_zones(state="available", opts=pulumi.InvokeOptions(provider=aws_provider, parent=null))
    azs = azs_info.names[:2]
    vpc = VPC(f"public-{region}", azs=azs, aws_provider=aws_provider, parent=null)
    vpc.create_subnets()
    vpc.create_internet_gateway()
    SecurityGroup(f"ec2-{region}", vpc_id=vpc.get_vpc_id(), description="Allow ssh inbound traffic", ingresses=[{"ip_protocol": "tcp", "cidr_ip": "0.0.0.0/0", "from_port": 22, "to_port": 22}], parent=null, aws_provider=aws_provider)
    #pulumi.export(f"ami_id_{region}", get_ami_id(aws_provider))
    #pulumi.export(f"vpc_id_{region}", get_vpc_id(aws_provider))


create_iam_role()
create_key_pair()
#create_s3_bucket(regions[0])
