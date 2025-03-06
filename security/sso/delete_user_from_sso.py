import boto3

# Remove sso assignment of permissionset to user in all organization accounts 

client = boto3.client('sso-admin')
PermissionSetArns = []


InstanceArn = ""
AccountId = ""


for PermissionSetArn in ["PermissionSetArns"]:
    response = client.list_account_assignments(
        AccountId=AccountId,
        InstanceArn=InstanceArn,
        MaxResults=100,
        PermissionSetArn=PermissionSetArn
    )


    for assignment in response['AccountAssignments']:
        if assignment['PrincipalType'] == 'USER':
            r = client.delete_account_assignment(
                InstanceArn=InstanceArn,
                PermissionSetArn=PermissionSetArn,
                PrincipalId=assignment['PrincipalId'],
                PrincipalType=assignment['PrincipalType'],
                TargetId=AccountId,
                TargetType='AWS_ACCOUNT'
            )
            print(r)
