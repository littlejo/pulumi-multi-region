STACK=deploy-ec2
AWS_REGIONS=eu-west-3,eu-north-1,ca-central-1,sa-east-1,ap-northeast-1,ap-southeast-2,af-south-1
S3_REGION=eu-west-3
INSTANCE_TYPE=c5a.large
FINAL_INSTANCE_TYPE=c5a.2xlarge
FINAL_REGION=eu-west-3
#AWS_REGIONS=us-east-1,us-west-2,ca-central-1,sa-east-1,eu-west-3,eu-west-1,eu-north-1,ap-northeast-1,ap-southeast-2,af-south-1,me-south-1

deploy:
	pulumi login $(BUCKET_S3)
	pulumi stack init $(STACK) || true
	pulumi config set --stack $(STACK) awsRegions $(AWS_REGIONS)
	pulumi config set --stack $(STACK) s3Region $(S3_REGION)
	pulumi config set --stack $(STACK) publicKey "$(PUBLIC_KEY)"
	pulumi config set --stack $(STACK) instanceType "$(INSTANCE_TYPE)"
	pulumi config set --stack $(STACK) finalInstanceType "$(FINAL_INSTANCE_TYPE)"
	pulumi config set --stack $(STACK) finalInstanceRegion "$(FINAL_REGION)"
	pulumi up --stack $(STACK)

destroy:
	pulumi down
