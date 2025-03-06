import boto3
import logging
import json
import re
import typer

logging.basicConfig(level=logging.INFO, format="%(levelname)s : %(message)s")


def update_cdn_distribution(client, cdn, config, etag):
    try:
        client.update_distribution(
            DistributionConfig=config,
            Id=cdn,
            IfMatch=etag
        )

        logging.info('Distribution ' + cdn + ' origins updated')
    except Exception as e:
        logging.error(e)


def get_all_distributions(client):
    origins_id = []
    try:
        response = client.list_distributions()
        origins = response['DistributionList']['Items']
        for origin in origins:
            origins_id.append(origin['Id'])

        return origins_id
    except Exception as e:
        logging.error(e)


def get_cdn_config(client, cdn):
    try:
        response = client.get_distribution_config(
            Id=cdn
        )

        logging.info('Configuration for ' + cdn + ' distribution obtained')
        return response
    except Exception as e:
        logging.error(e)


def get_bucket_name_from_endpoint(endpoint):
    match = re.match('^(.*?)\.', endpoint)  # prendo il nome delle risorsa dal domain
    resource = match.group().rstrip(match.group()[-1])  # leva il punto finale, da aggiustare la regex

    return resource


def make_name_valid_for_search(bucket, src_env_name, dst_env_name):
    name = ''.join(i for i in bucket if not i.isdigit())
    name = name.replace(src_env_name, dst_env_name)

    return name


def get_buckets_by_prefix(session, prefix):
    s3 = session.client('s3')
    paginator = s3.get_paginator('list_buckets')
    page_iterator = paginator.paginate()
    filtered_iterator = page_iterator.search(f'Buckets[?starts_with(Name, `{prefix}`)].Name')
    resource = list(filtered_iterator)

    return resource[0]


def get_cdn_arn(client, cdn):
    try:
        responce = client.get_distribution(
            Id=cdn
        )

        return responce['Distribution']['ARN']
    except Exception as e:
        logging.error(e)


def remove_cdn_waf_tag(client, cdn_arn):
    try:
        response = client.untag_resource(
            Resource=cdn_arn,
            TagKeys={
                'Items': [
                    'WebACL'
                ]
            }
        )

    except Exception as e:
        logging.error(e)


def add_cdn_waf_tag(client, cdn_arn):
    try:
        response = client.tag_resource(
            Resource=cdn_arn,
            Tags={
                'Items': [
                    {
                        'Key': 'WebACL',
                        'Value': 'Centralized-Public-Base-Global'
                    }
                ]
            }
        )

    except Exception as e:
        logging.error(e)


def get_webaclid_arn(session, name, id):
    wafv2 = session.client('wafv2')

    response = wafv2.get_web_acl(
        Name=name,
        Scope='CLOUDFRONT',
        Id=id
    )

    webAclArn = response['WebACL']['ARN']
    return webAclArn


# ToDo
# 1) Chiamare update distribution solo se ci sono dei cambiamenti nella config
# 2) Mettere la possibilità di chiedere conferma per i cambiamenti della configurazione
def update_cdn_with_json(profile: str = typer.Argument(..., help="AWS profile for auth"),
                         region: str = typer.Argument(..., help="AWS region for auth")):
    session = boto3.Session(profile_name=profile, region_name=region)
    cloudfront = session.client('cloudfront')

    with open('distributions.json', 'r') as file:
        data = json.load(file)

    if len(data) > 0:
        for cdn in data:
            if 'distribution_id' in cdn.keys():
                try:
                    cdn_id = cdn['distribution_id']
                    input_size = len([True for x in cdn if x != 'distribution_id'])
                    config = get_cdn_config(cloudfront, cdn_id)

                    cdn_config = config['DistributionConfig']
                    etag = config['ETag']

                    quantity = cdn_config['Origins']['Quantity']
                    items = cdn_config['Origins']['Items']

                    if input_size <= quantity or input_size != 0:

                        for origin in items:
                            origin_name = origin['Id']

                            if origin_name in cdn:
                                origin['DomainName'] = cdn[origin_name]
                            else:
                                logging.info(
                                    'Skipping origin ' + origin_name + ' in distribution ' + cdn_id + ' due to missing input')

                        update_cdn_distribution(cloudfront, cdn_id, cdn_config, etag)
                    else:
                        logging.error('Skipping cdn ' + cdn_id + ' because max ' + str(
                            quantity) + ' origins expected or none given')
                except Exception as e:
                    logging.error(e + ' occurred during the update of distribution ' + cdn_id + ', skipping...')
            else:
                logging.error('Missing distribution_id key')
    else:
        logging.error('Empty json input file')
        raise SystemExit(1)


#ToDo
#1) Fare switch della web acl solo se sono forniti name e id, controllare che se uno è fornito lo sia anche l'altro
def update_all_cdns(profile: str = typer.Argument(..., help="AWS profile for auth"),
                    src_region: str = typer.Argument(..., help="Source AWS region for auth"),
                    dst_region: str = typer.Argument(..., help="Destination AWS region for auth"),
                    src_env_name: str = typer.Argument(..., help="Source terraform environment name"),
                    dst_env_name: str = typer.Argument(..., help="Destination terraform environment name"),
                    be: str = typer.Argument(..., help="DNS name of the alb used for backend"),
                    web_acl_name: str = typer.Argument(...,
                                                       help="Name of the Web ACL you want to use for distribution"),
                    web_acl_id: str = typer.Argument(..., help="Id of the Web ACL you want to use for distribution"),
                    origin_name_to_skip: str = typer.Argument(..., help="Comma separated list to origin name to skip")):
    session_dst = boto3.Session(profile_name=profile, region_name=dst_region)
    session_cdn = boto3.Session(profile_name=profile, region_name='us-east-1')

    origin_name_to_skip = origin_name_to_skip.split(',')

    # Prendo l'arn della web acl
    webAclArn = get_webaclid_arn(session_cdn, web_acl_name, web_acl_id)

    cloudfront_client = session_dst.client('cloudfront')
    cdns = get_all_distributions(cloudfront_client)

    for cdn in cdns:
        # Rimuovo il tag del waf centralizzato
        cdn_arn = get_cdn_arn(cloudfront_client, cdn)
        remove_cdn_waf_tag(cloudfront_client, cdn_arn)

        config = get_cdn_config(cloudfront_client, cdn)
        cdn_config = config['DistributionConfig']
        etag = config['ETag']

        # Modifico la web acl id
        cdn_config['WebACLId'] = webAclArn

        items = cdn_config['Origins']['Items']

        for origin in items:
            try:
                origin_domain = origin['DomainName']

                if dst_env_name in origin_domain:
                    logging.info(
                        'Skipping origin ' + origin_domain + ' in distribution ' + cdn + ' because already updated')
                else:
                    if origin_domain not in origin_name_to_skip and (
                            '.s3.' in origin_domain or '.s3-' in origin_domain):

                        src_bucket_name = get_bucket_name_from_endpoint(
                            origin_domain)  #Prendo il nome del bucket dal domain name dell'origin
                        valid_src_bucket_name = make_name_valid_for_search(src_bucket_name, src_env_name,
                                                                           dst_env_name)  #Tolgo i numeri dal nome del bucket e cambio il nome dell'environment
                        dst_resource = get_buckets_by_prefix(session_dst,
                                                             valid_src_bucket_name)  #Prendo il bucket corrispondente di dr con il nome ottenuto prima

                        origin_domain = origin_domain.replace(src_region,
                                                              dst_region)  #sotituisco la region nel domain name dell'origin
                        origin['DomainName'] = origin_domain.replace(src_bucket_name, dst_resource)
                    elif '.elb.' in origin_domain:
                        origin['DomainName'] = be
            except Exception:
                logging.error("Error while updating cdn " + cdn)

        update_cdn_distribution(cloudfront_client, cdn, cdn_config, etag)


#ToDo
#1) Cambiare logica
#Passo le variabili src e dst in modo inverso alle funzioni rispetto a update_all_cdns
def revert_update_all_cdns(profile: str = typer.Argument(..., help="AWS profile for auth"),
                           src_region: str = typer.Argument(..., help="Source AWS region for auth"),
                           dst_region: str = typer.Argument(..., help="Destination AWS region for auth"),
                           src_env_name: str = typer.Argument(..., help="Source terraform environment name"),
                           dst_env_name: str = typer.Argument(..., help="Destination terraform environment name"),
                           be: str = typer.Argument(..., help="DNS name of the alb used for backend"),
                           origin_name_to_skip: str = typer.Argument(..., help="Comma separated list to origin name to skip")):


    session_dst = boto3.Session(profile_name=profile, region_name=dst_region)

    cloudfront_client = session_dst.client('cloudfront')
    cdns = get_all_distributions(cloudfront_client)

    origin_name_to_skip = origin_name_to_skip.split(',')


    for cdn in cdns:
        #Aggiungo il tag del waf centralizzato
        cdn_arn = get_cdn_arn(cloudfront_client, cdn)
        add_cdn_waf_tag(cloudfront_client, cdn_arn)

        config = get_cdn_config(cloudfront_client, cdn)
        cdn_config = config['DistributionConfig']
        etag = config['ETag']

        items = cdn_config['Origins']['Items']

        for origin in items:
            try:
                origin_domain = origin['DomainName']

                if dst_env_name not in origin_domain:
                    logging.info(
                        'Skipping origin ' + origin_domain + ' in distribution ' + cdn + ' because already updated')
                else:
                    if origin_domain not in origin_name_to_skip  and (
                            '.s3.' in origin_domain or '.s3-' in origin_domain):

                        src_bucket_name = get_bucket_name_from_endpoint(
                            origin_domain)  #Prendo il nome del bucket dal domain name dell'origin
                        valid_src_bucket_name = make_name_valid_for_search(src_bucket_name, dst_env_name,
                                                                           src_env_name)  #Tolgo i numeri dal nome del bucket e cambio il nome dell'environment
                        dst_resource = get_buckets_by_prefix(session_dst,
                                                             valid_src_bucket_name)  #Prendo il bucket corrispondente di primario con il nome ottenuto prima

                        origin_domain = origin_domain.replace(dst_region,
                                                              src_region)  #sotituisco la region nel domain name dell'origin
                        origin['DomainName'] = origin_domain.replace(src_bucket_name, dst_resource)
                    elif '.elb.' in origin_domain:
                        origin['DomainName'] = be
            except Exception:
                logging.error('Error while updating cdn ' + cdn)

        update_cdn_distribution(cloudfront_client, cdn, cdn_config, etag)


def update_all_cdns_tls_version(profile: str = typer.Argument(..., help="AWS profile for auth"),
                                tls_version: str = typer.Argument(...,
                                                                  help="TLS version you want to apply on all cdns")):
    session_cdn = boto3.Session(profile_name=profile, region_name='us-east-1')
    cloudfront_client = session_cdn.client('cloudfront')

    #Controllo che la versione di tls fornita sia valida
    valid_tls_versions = ['SSLv3', 'TLSv1', 'TLSv1_2016', 'TLSv1.1_2016', 'TLSv1.2_2018', 'TLSv1.2_2019',
                          'TLSv1.2_2021']
    if tls_version not in valid_tls_versions:
        logging.error(
            'Invalid TLS version provided, valid version are: {}'.format(', '.join(map(str, valid_tls_versions))))
        raise SystemExit(1)

    cdns = get_all_distributions(cloudfront_client)

    for cdn in cdns:
        try:
            config = get_cdn_config(cloudfront_client, cdn)
            cdn_config = config['DistributionConfig']
            etag = config['ETag']

            current_tls_version = cdn_config['ViewerCertificate']['MinimumProtocolVersion']
            logging.info('Cdn ' + cdn + ' current TLS version: ' + current_tls_version)
            if tls_version == current_tls_version:
                logging.info('Skipping cdn ' + cdn + ' because TLS is already ' + tls_version)
            else:
                cdn_config['ViewerCertificate']['MinimumProtocolVersion'] = tls_version
                update_cdn_distribution(cloudfront_client, cdn, cdn_config, etag)
                logging.info('Cdn ' + cdn + ' tls version has been updated')
        except Exception:
            logging.error('Error while updating cdn ' + cdn)
