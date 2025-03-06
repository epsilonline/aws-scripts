from importlib.metadata import distribution

import boto3
from pathlib import Path
import csv

from cloudfront.function import get_all_distributions


def update_web_acl_for_all_distribution(web_acl_id: str, profile: str = "default",
                                        force_set_web_acl: bool = True, cdn_list_path: str = None):
    session = boto3.Session(profile_name=profile)
    cloudfront_client = session.client('cloudfront')

    distribution_id_list = []

    if not cdn_list_path:
        distribution_id_list = get_all_distributions(cloudfront_client)
    else:
        cloudfront_csv_file_path = Path(cdn_list_path)
        with open(cloudfront_csv_file_path) as csvfile:
            file_reader = csv.reader(csvfile, delimiter=',')
            for row in file_reader:
                distribution_id = row[0]
                distribution_id_list += [distribution_id]

    for distribution_id in distribution_id_list:
        distribution_config = cloudfront_client.get_distribution_config(
            Id=distribution_id
        )
        if_match = distribution_config['ETag']
        distribution_config = distribution_config['DistributionConfig']
        if not distribution_config.get('WebACLId') or force_set_web_acl:
            print(f"Set webACL for distribution: {distribution_id}")
            distribution_config['WebACLId'] = web_acl_id

            response = cloudfront_client.update_distribution(DistributionConfig=distribution_config,
                                                             Id=distribution_id, IfMatch=if_match)
            print(f"webACLId updated for distribution: {response['Distribution']['Id']}")
