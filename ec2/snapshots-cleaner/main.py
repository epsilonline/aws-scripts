#!/usr/local/bin/python3
import csv
import re
from collections import OrderedDict
from pprint import pprint

import boto3
import click
from botocore.exceptions import ClientError

regions = ['eu-west-1']


ec2 = None
exists_icon = '✅'
not_exists_icon = '❌'


@click.group()
def cli():
    '''
    Helper commands for Snapshots management.
    '''
    pass


@cli.command()
def snapshot_report():
    '''
    Find unreferenced snapshots.
    '''
    global ec2
    with open('report.csv', 'w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow([
            'id',
            'volume_id',
            'volume_exists',
            'ami_id',
            'ami_exists',
            'instance_id',
            'instance_exists',
            'size',
            'start_time',
            'description'])
        for region in regions:
            ec2 = boto3.client('ec2', region_name=region)
            for snapshot in get_snapshots():
                csv_writer.writerow([
                    snapshot['id'],
                    snapshot['volume_id'],
                    snapshot['volume_exists'],
                    snapshot['ami_id'],
                    snapshot['ami_exists'],
                    snapshot['instance_id'],
                    snapshot['instance_exists'],
                    str(snapshot['size']) + 'gb',
                    str(snapshot['start_time']),
                    snapshot['description']])

@cli.command()
def snapshot_cleanup():
    '''
    Find and delete unreferenced snapshots.
    '''
    global ec2
    print('{:22} {:23} {:23} {:23} {:>7} {:25} {:30}'.format('snapshot id', 'volume id', 'ami id',
                                                             'instance id', 'size', 'start time', 'description'))

    for region in regions:
        ec2 = boto3.client('ec2', region_name=region)
        print('region={}'.format(region))
        for snapshot in get_snapshots():
            volume_exists = exists_icon if snapshot['volume_exists'] else not_exists_icon
            ami_exists = exists_icon if snapshot['ami_exists'] else not_exists_icon
            instance_exists = exists_icon if snapshot['instance_exists'] else not_exists_icon
            print('{:22} {:22} {:22} {:22} {:>7} {:25} {:30}'.format(
                snapshot['id'],
                snapshot['volume_id'] + volume_exists,
                snapshot['ami_id'] + ami_exists,
                snapshot['instance_id'] + instance_exists,
                str(snapshot['size']) + 'gb',
                str(snapshot['start_time']),
                snapshot['description']
            ))
            # if not snapshot['volume_exists'] and not snapshot['ami_exists'] and not snapshot['instance_exists'] and click.confirm('Delete?', default=True):
            if not snapshot['ami_exists'] and "backup" not in snapshot['description'].lower() and "copied" not in snapshot['description'].lower():
                ec2.delete_snapshot(SnapshotId=snapshot['id'])


@cli.command()
def volume_cleanup():
    '''
    Find and delete unused volumes.
    '''
    global ec2
    print('{:23} {:20} {:>7} {:10} {:23}'.format(
        'volume id', 'status', 'size', 'created', 'snapshot id'))

    for region in regions:
        ec2 = boto3.client('ec2', region_name=region)
        print('region={}'.format(region))
        for volume in get_available_volumes():
            snapshot_exists = exists_icon if volume['snapshot_exists'] else not_exists_icon
            print('{:23} {:20} {:>7} {:10} {:22}'.format(
                volume['id'],
                volume['status'],
                str(volume['size']) + 'gb',
                volume['create_time'].strftime('%Y-%m-%d'),
                volume['snapshot_id'] + snapshot_exists

            ))
            if not volume['snapshot_exists']:
                print('Tags:')
                print('  '+('\n  '.join(['{}={}'.format(click.style(key, fg='blue'), tag)
                                         for key, tag in volume['tags'].items()])))
                if click.confirm('Delete?', default=True):
                    ec2.delete_volume(VolumeId=volume['id'])


@cli.command()
@click.argument('snapshot_id')
def snapshot_delete(snapshot_id):
    '''
    Delete single snapshot by id.
    '''
    try:
        ec2.delete_snapshot(SnapshotId=snapshot_id)
        print('Deleted ' + snapshot_id)
    except ClientError as e:
        print('Failed to delete ' + snapshot_id)
        print(e)


def get_snapshots():
    '''
    Get all snapshots.
    '''
    for snapshot in ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']:
        instance_id, image_id = parse_description(snapshot['Description'])
        yield {
            'id': snapshot['SnapshotId'],
            'description': snapshot['Description'],
            'start_time': snapshot['StartTime'],
            'size': snapshot['VolumeSize'],
            'volume_id': snapshot['VolumeId'],
            'volume_exists': volume_exists(snapshot['VolumeId']),
            'instance_id': instance_id,
            'instance_exists': instance_exists(instance_id),
            'ami_id': image_id,
            'ami_exists': image_exists(image_id),
        }


def get_available_volumes():
    '''
    Get all volumes in 'available' state. (Volumes not attached to any instance)
    '''
    for volume in ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])['Volumes']:
        yield {
            'id': volume['VolumeId'],
            'create_time': volume['CreateTime'],
            'status': volume['State'],
            'size': volume['Size'],
            'snapshot_id': volume['SnapshotId'],
            'snapshot_exists': str(snapshot_exists(volume['SnapshotId'])),
            'tags': OrderedDict(sorted([(tag['Key'], tag['Value']) for tag in volume['Tags']])),
        }


def snapshot_exists(snapshot_id):
    if not snapshot_id:
        return ''
    try:
        ec2.describe_snapshots(SnapshotIds=[snapshot_id])
        return True
    except ClientError:
        return False


def volume_exists(volume_id):
    if not volume_id:
        return False
    try:
        ec2.describe_volumes(VolumeIds=[volume_id])
        return True
    except ClientError:
        return False


def instance_exists(instance_id):
    if not instance_id:
        return ''
    try:
        return len(ec2.describe_instances(InstanceIds=[instance_id])['Reservations']) != 0
    except ClientError:
        return False


def image_exists(image_id):
    if not image_id:
        return ''
    try:
        return len(ec2.describe_images(ImageIds=[image_id])['Images']) != 0
    except ClientError:
        return False


# Return instance_id, ami_id
def parse_description(description):
    regex = r"^Created by CreateImage\((.*?)\) for (ami-.*)"
    matches = re.finditer(regex, description, re.MULTILINE)
    for matchNum, match in enumerate(matches):
        instance_id, ami_id = match.groups()
        return instance_id, ami_id.split(' ')[0]
    return '', ''


if __name__ == '__main__':
    cli()
