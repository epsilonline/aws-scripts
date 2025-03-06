import os
from email.quoprimime import body_decode

import boto3
import requests
from requests_aws4auth import AWS4Auth
import json


def print_json_response(response):
    if type(response) == requests.models.Response:
        msg = json.loads(response.text)
    elif response is str:
        msg = json.loads(response)
    else:
        msg = response
    print(json.dumps(msg, indent=2, sort_keys=False))


def aws_auth(profile=None, region=None, service="es"):
    profile = profile or os.getenv('AWS_PROFILE', "default")
    region = region or os.getenv('AWS_REGION', None)
    session = boto3.Session(profile_name=profile, region_name=region)
    _region = session.region_name
    os.environ['AWS_REGION'] = _region
    credentials = session.get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, _region, service,
                       session_token=credentials.token)

    return awsauth


def register_repository(awsauth, host, repository_name, base_path, bucket_to_register, role_access_to_bucket):
    path = '_snapshot/' + repository_name
    url = host + path

    payload = {
        "type": "s3",
        "settings": {
            "bucket": bucket_to_register,
            "base_path": base_path,
            "region": os.environ['AWS_REGION'],
            "role_arn": role_access_to_bucket
        }
    }

    headers = {"Content-Type": "application/json"}

    r = requests.post(url, auth=awsauth, json=payload, headers=headers)

    print_json_response(r)


def trigger_snapshot(awsauth, host, repository_name, snapshot_name):
    path = '_snapshot/' + repository_name + '/' + snapshot_name
    url = host + path

    r = requests.put(url, auth=awsauth)

    print_json_response(r)


def snapshot_status_cmd(awsauth, host):
    path = '_snapshot/*'
    url = host + path
    r = requests.get(url, auth=awsauth)
    print_json_response(r)


def _snapshot_info(awsauth, host, repository_name, snapshot_name):
    path = f'_snapshot/{repository_name}/{snapshot_name}'
    url = host + path
    r = requests.get(url, auth=awsauth)
    snapshots = json.loads(r.text).get('snapshots', [])
    return snapshots[0] if len(snapshots) > 0 else None


def snapshot_info_cmd(awsauth, host, repository_name, snapshot_name):
    print_json_response(_snapshot_info(awsauth, host, repository_name, snapshot_name))


def restore_snapshot_cmd(awsauth, host, repository_name, snapshot_name, skip_restore_of_hidden_index: True):
    # Get index list in snapshot
    snapshot_to_restore = _snapshot_info(awsauth=awsauth, host=host, repository_name=repository_name,
                                         snapshot_name=snapshot_name)
    index_in_snapshot = snapshot_to_restore.get('indices', [])
    # Check which index can be restored
    index_to_restore = list(filter(lambda x: not x.startswith('.'),index_in_snapshot)) if skip_restore_of_hidden_index \
                            else index_in_snapshot
    # Restore
    path = '_snapshot/' + repository_name + '/' + snapshot_name + '/' + '_restore'
    url = host + path
    payload = {
        "indices": ",".join(index_to_restore),
        "include_global_state": False
    }

    headers = {"Content-Type": "application/json"}

    r = requests.post(url, auth=awsauth, json=payload, headers=headers)

    print_json_response(r)


def deregister_repository(awsauth, host, repository_name):
    path = '_snapshot/' + repository_name
    url = host + path
    r = requests.delete(url, auth=awsauth)
    print_json_response(r)


def snapshot_list_cmd(awsauth, host: str, repository: str):
    path = f"_snapshot/{repository}/*"
    url = host + path
    r = requests.get(url, auth=awsauth)
    print_json_response(r)


def _get_latest_snapshot(awsauth, host: str, repository: str):
    path = f"_snapshot/{repository}/*"
    url = host + path
    r = requests.get(url, auth=awsauth)
    snapshot_list = json.loads(r.text).get('snapshots', [])
    if len(snapshot_list) > 0:
        snapshot_list_sorted = sorted(snapshot_list, key=lambda x: x["end_time_in_millis"], reverse=True)
        latest_snapshot = snapshot_list_sorted[0]
        return latest_snapshot
    else:
        return None


def get_latest_snapshot_cmd(awsauth, host: str, repository: str):
    print(
        json.dumps(_get_latest_snapshot(awsauth=awsauth, host=host, repository=repository), indent=2, sort_keys=False))


def restore_latest_snapshot_cmd(awsauth, host: str, repository: str, skip_restore_of_hidden_index: True):
    latest_snapshot = _get_latest_snapshot(awsauth=awsauth, host=host, repository=repository)
    if latest_snapshot:
        restore_snapshot_cmd(awsauth=awsauth, host=host, repository_name=repository,
                             snapshot_name=latest_snapshot['snapshot'],
                             skip_restore_of_hidden_index=skip_restore_of_hidden_index)
    else:
        print("No snapshot available")


def create_snapshot_policy(awsauth, host: str, policy_name: str, repository_name: str, schedule_expression: str,
                           timezone: str = "UTC"):
    path = f"_plugins/_sm/policies/{policy_name}/"
    url = host + path
    body = {
      "description": f"{policy_name}",
      "creation": {
        "schedule": {
          "cron": {
            "expression": schedule_expression,
            "timezone": timezone
          }
        },
        "time_limit": "1h"
      },
      "snapshot_config": {
        "date_format": "yyyy-MM-dd-HH:mm",
        "timezone": timezone,
        "indices": "*",
        "repository": repository_name,
        "ignore_unavailable": "true",
        "include_global_state": "false",
        "partial": "true",
      },
    }

    r = requests.post(url, auth=awsauth, json=body)
    print_json_response(r)
