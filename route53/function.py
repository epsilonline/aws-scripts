import boto3
from datetime import datetime


def export_route53_zone(hosted_zone_id: str, output_file: str = None):
    """
    Export route 53 zone in file
    """
    try:
        # Initialize Route 53 client
        client = boto3.client("route53")

        # Fetch Hosted Zone details
        zone = client.get_hosted_zone(Id=hosted_zone_id)
        zone_name = zone["HostedZone"]["Name"]

        # Fetch all records in the Hosted Zone
        paginator = client.get_paginator("list_resource_record_sets")
        record_sets = paginator.paginate(HostedZoneId=hosted_zone_id)

        # Create zone file content
        zone_file = f"; Zone file for {zone_name}\n"
        zone_file += f"; Exported on {datetime.utcnow().isoformat()} UTC\n\n"

        for page in record_sets:
            for record in page["ResourceRecordSets"]:
                record_name = record["Name"]
                record_type = record["Type"]
                ttl = f"{record.get('TTL', '300')}s"
                resource_records = record.get("ResourceRecords", [])

                # Format the record line
                for resource_record in resource_records:
                    value = resource_record["Value"]
                    zone_file += f"{record_name}\t{ttl}\tIN\t{record_type}\t{value}\n"

                # Handle Alias records
                if "AliasTarget" in record:
                    alias = record["AliasTarget"]["DNSName"]
                    zone_file += f"{record_name}\t{ttl}\tIN\t{record_type}\t{alias} ; Alias\n"

        # Save to file
        output_file = output_file or f"{hosted_zone_id}_zone_file.txt"
        with open(output_file, "w") as file:
            file.write(zone_file)

    except Exception as e:
        print(f"Error: {e}")