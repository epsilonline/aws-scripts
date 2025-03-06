import boto3
import typer


def check_bucket_versioning(account_profile: str = typer.Argument(..., help="Aws Profile"),
                            region: str = typer.Argument(..., help="Aws Region")):

    session = boto3.Session(profile_name=account_profile, region_name=region)
    s3 = session.client('s3', region_name=region)

    buckets = s3.list_buckets()

    versioned_buckets = []

    print("Finding buckets with enabled versioning..\n")
    for bucket in buckets['Buckets']:

        bucket_name = bucket['Name']
        bucket_location = s3.get_bucket_location(Bucket=bucket_name)['LocationConstraint']

        try:

            if bucket_location == region and "website" not in bucket_name.lower() and "src" not in bucket_name.lower() and "source" not in bucket_name.lower():
                versioning = s3.get_bucket_versioning(Bucket=bucket_name)
                
                if 'Status' in versioning and versioning['Status'] == 'Enabled':
                    versioned_buckets.append(bucket_name)
        except Exception as e:
            print(f"Cannot determine if versioning it's enabled for bucket '{bucket_name}': {str(e)}")

    if versioned_buckets:
        print("Buckets with enabled versioning:\n")
        for bucket in versioned_buckets:
            print(bucket)
    else:
        print("No bucket found with enabled versioning\n")
