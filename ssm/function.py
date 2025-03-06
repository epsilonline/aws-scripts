import boto3

import typer


def find_parameters(prefix: str = typer.Argument(..., help="SSM Path Prefix"),
                    value_to_find: str = typer.Argument(..., help="SSM value to find"),
                    region: str = typer.Argument(..., help="Region"),
                    profile: str = typer.Argument(..., help="AWS profile"),
                    exact_match: bool = typer.Argument(False,
                                                      help="If true find parameters that match exactly the required value")):
    parameters = get_parameters_by_prefix(prefix=prefix, region=region, profile=profile)
    match_params = []

    for param in parameters:
        if param['Value'] == value_to_find and exact_match:
            match_params.append(param['Name'])
        if param['Value'] == value_to_find and not exact_match:
            match_params.append(param['Name'])
    if match_params:
        print(f"\nParameters with value {value_to_find} in region {region}:\n")
        for param in match_params:
            print(param)
    else:
        print(f"\nNo parameter founds with value {value_to_find} in region {region}.\n")


def get_parameters_by_prefix(prefix, region, profile):
    session = boto3.Session(profile_name=profile)
    ssm = session.client('ssm', region_name=region)

    parameters = []
    next_token = True

    # Manage pagination
    while next_token:
        request_params = {
            'Path': prefix,
            'Recursive': True,
            'WithDecryption': True
        }

        if next_token:
            request_params['NextToken'] = next_token

        response = ssm.get_parameters_by_path(**request_params)

        parameters.extend(response['Parameters'])

        next_token = response.get('NextToken')

    return parameters
