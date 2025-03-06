"""
Check if cloudfront distributions have insecure configurations
Find distribution with S3 Origin that have Origin Access Identity and have insecure configuration.
"""
import os
import boto3
import json
import logging

logging.basicConfig()
logger = logging.getLogger('main')
logger.setLevel(os.getenv('LOG_LEVEL') or 'INFO')

cloudfront_client = boto3.client('cloudfront')
s3_client = boto3.client('s3')

insecure_methods = ['DELETE', 'PUT']


def s3_origin_with_oai(distribution: dict):
    """
    Find s3 origins with OAI
    :param distribution:
    :return: Return list of dict with distribution id and bucket name that have OAI
    """
    s3_origins_with_oai = []
    origins = distribution.get('Origins', {}).get('Items', [])
    for origin in origins:
        if origin.get('S3OriginConfig', {}).get('OriginAccessIdentity', ''):
            bucket_name = origin['DomainName'].split('.')[0]
            behaviors = [distribution.get('DefaultCacheBehavior', {}), distribution.get('CacheBehaviors', {})]
            behavior = list(filter(lambda x: x.get('TargetOriginId', '') == origin.get('Id', None), behaviors))[0]
            s3_origins_with_oai.append({'id': distribution['Id'], 'bucket': bucket_name, 'behavior': behavior,
                                        'Aliases': distribution.get('Aliases', {}).get('Items', [])})
    return s3_origins_with_oai


def check_security_configuration(distribution_with_oai: dict):
    """
    Check if bucket have insecure configuration
    :param distribution_with_oai:
    :return: input dict if associated bucket have insecure policy, None otherwise
    """
    bucket_name = distribution_with_oai['bucket']
    distribution_id = distribution_with_oai['id']
    bucket_policy = s3_client.get_bucket_policy(Bucket=bucket_name)
    # each if statement can be update the psi attribute of distribution_with_oai
    # psi: is acronym of possible security issue
    distribution_with_oai['psi'] = []
    if have_insecure_action(bucket_policy['Policy']):
        logger.debug(f'{bucket_name} have insecure policy')
        distribution_with_oai['psi'].append("insecure_policy")
        return distribution_with_oai
    if have_insecure_method(distribution_with_oai):
        logger.debug(f'{distribution_id} have insecure method: f{insecure_methods}')
        distribution_with_oai['psi'].append("insecure_method")
        return distribution_with_oai
    if have_insecure_restrict_viewer(distribution_with_oai):
        logger.debug(f'{distribution_id} have insecure access viewer')
        distribution_with_oai['psi'].append("insecure_access_viewer")
        return distribution_with_oai
    return None


def have_insecure_action(bucket_policy: str):
    """
    check if statements have actions with '*'
    :param bucket_policy: bucket policy of origin associated to behavior with OAI
    :return: true if at least one action have '*' character
    """
    policy = json.loads(bucket_policy)
    for statement in policy.get('Statement', []):
        logger.debug(statement.get('Action', []))
        for a in statement.get('Action', []):
            if '*' in a:
                return True
    return False


def have_insecure_method(distribution_with_oai: dict):
    """
    check behavior allow insecure method
    :param distribution_with_oai
    :return: true if behavior have insecure method
    """
    behavior = distribution_with_oai.get('behavior', {})
    for m in insecure_methods:
        if m in behavior.get('AllowedMethods', {}).get('Items', []):
            return True
    return False


def have_insecure_restrict_viewer(distribution_with_oai: dict):
    """
    check behavior with oai have a trusted signers or trusted key groups disabled
    :param distribution_with_oai: policy
    :return: true if behavior with oai have a trusted signers or trusted key groups disabled
    """
    behavior = distribution_with_oai.get('behavior', {})
    if not (behavior.get('TrustedSigners', {}).get('Enabled', False) or \
            behavior.get('TrustedKeysGroups', {}).get('Enabled', False)):
        return True
    return False


def main():
    next_page = True
    next_maker = ''
    distributions_with_oai = []

    # Get all distributions with oai
    while next_page:
        response = cloudfront_client.list_distributions(Marker=next_maker)

        next_page = next_maker = response.get('DistributionList', {}).get('NextMarker', None)
        distributions = response.get('DistributionList', {}).get('Items', [])
        distributions_with_oai += [item for sublist in list(map(s3_origin_with_oai, distributions)) for item in sublist]

    logger.info(f"Distributions with OAI: \n{[x.get('id', '') for x in distributions_with_oai]}")
    vulnerable_distributions = [{'id': x['id'], 'aliases': x['Aliases'], 'psi': x['psi']} for x in
                                list(map(check_security_configuration, distributions_with_oai)) if x]
    logger.debug(f"Vulnerable distribution with OAI: \n {vulnerable_distributions}")
    for v in vulnerable_distributions:
        logger.info(f"[{v.get('id', '')} -> {v.get('aliases', [])}] can be have this issues: "
                    f"{v.get('psi', '')}")


if __name__ == '__main__':
    main()
