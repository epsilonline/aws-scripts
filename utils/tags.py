from utils.aws import AWSHelper
from typing import Union


def get_resources_arn_by_tags(tags, resource_type_filters: Union[str, list[str]]) -> list[str]:
    client = AWSHelper.get_client('resourcegroupstaggingapi')
    paginator = client.get_paginator('get_resources')

    resources = []

    tag_filters = []

    if type(resource_type_filters) is str:
        resource_type_filters = [resource_type_filters]
    elif type(resource_type_filters) is list:
        resource_type_filters = resource_type_filters
    else:
        raise ValueError('Invalid resource type')

    for k, v in tags.items():
        if type(v) is str:
            tag_filters.append({'Key': k, 'Values': [v]})
        elif type(v) is list:
            tag_filters.append({'Key': k, 'Values': v})
        else:
            raise ValueError('Invalid tag value')

    response_iterator = paginator.paginate(TagFilters=tag_filters, ResourceTypeFilters=resource_type_filters)

    for page in response_iterator:
        resource_tag_mapping_list = page['ResourceTagMappingList']
        for resource in resource_tag_mapping_list:
            resources.append(resource['ResourceARN'])
    return resources
