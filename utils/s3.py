from typing import List
from utils.tags import get_resources_arn_by_tags


def get_buckets_by_tag(tag_key: str, tag_value: str) -> List[str]:
    """
    Returns a list of bucket names that match the specified tag.

    Args:
        tag_key: The tag key to search for.
        tag_value: The tag value to search for.

    Returns:
        A list of bucket names that have the matching tag.
    """
    resource_type_filters = 's3:bucket'
    resources = get_resources_arn_by_tags(tags={tag_key: tag_value}, resource_type_filters=resource_type_filters)
    resources = [r.split(':')[-1] for r in resources]
    return resources
