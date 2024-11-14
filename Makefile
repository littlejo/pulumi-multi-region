STACK=deploy-ec2
AWS_REGIONS=us-east-1,us-west-2
S3_REGION=us-west-2
#AWS_REGIONS=us-east-1,us-west-2,ca-central-1,sa-east-1,eu-west-3,eu-west-1,eu-north-1,ap-northeast-1,ap-southeast-2,af-south-1,me-south-1

deploy:
	pulumi login $(BUCKET_S3)
	pulumi stack init $(STACK) || true
	pulumi config set --stack $(STACK) awsRegions $(AWS_REGIONS)
	pulumi config set --stack $(STACK) s3Region $(S3_REGION)
	pulumi config set --stack $(STACK) publicKey "$(PUBLIC_KEY)"
	pulumi up --stack $(STACK)

destroy:
	pulumi down
