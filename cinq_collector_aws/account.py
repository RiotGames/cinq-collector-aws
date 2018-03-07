from collections import defaultdict

from botocore.exceptions import ClientError
from cloud_inquisitor import get_aws_session
from cloud_inquisitor.config import dbconfig
from cloud_inquisitor.database import db
from cloud_inquisitor.plugins import BaseCollector, CollectorType
from cloud_inquisitor.plugins.types.resources import S3Bucket, CloudFrontDist, DNSZone, DNSRecord
from cloud_inquisitor.schema.base import Account
from cloud_inquisitor.utils import get_resource_id
from cloud_inquisitor.wrappers import retry


class AWSAccountCollector(BaseCollector):
    name = 'EC2 Account Collector'
    ns = 'collector_ec2'
    type = CollectorType.AWS_ACCOUNT
    interval = dbconfig.get('interval', ns, 15)

    def __init__(self, account):
        super().__init__()

        if type(account) == str:
            account = Account.get(account)

        self.account = account
        self.session = get_aws_session(self.account)

    def run(self):
        try:
            self.update_s3buckets()
            self.update_cloudfront()
            self.update_route53()
        except Exception as ex:
            self.log.exception(ex)
            raise
        finally:
            del self.session

    @retry
    def update_s3buckets(self):
        """Update list of S3 Buckets for the account

        Returns:
            `None`
        """
        self.log.debug('Updating S3Buckets for {}'.format(self.account.account_name))
        s3 = self.session.resource('s3')

        try:
            existing_buckets = S3Bucket.get_all(self.account)
            buckets = {bucket.name: bucket for bucket in s3.buckets.all()}

            for data in buckets.values():
                if data.name in existing_buckets:
                    bucket = existing_buckets[data.name]
                    if bucket.update(data):
                        self.log.debug('Change detected for S3Bucket {}/{}'.format(
                            self.account.account_name,
                            bucket.id
                        ))
                        bucket.save()
                else:
                    properties = {
                        'creation_date': data.creation_date
                    }

                    # If a bucket has no tags, a boto3 error is thrown. We treat this as an empty tag set
                    try:
                        tags = {t['Key']: t['Value'] for t in data.Tagging().tag_set}
                    except ClientError:
                        tags = {}

                    S3Bucket.create(
                        data.name,
                        account_id=self.account.account_id,
                        properties=properties,
                        tags=tags
                    )
                    self.log.debug('Added new S3Bucket {}/{}'.format(
                        self.account.account_name,
                        data.name
                    ))
            db.session.commit()

            bk = set(list(buckets.keys()))
            ebk = set(list(existing_buckets.keys()))

            try:
                for resource_id in ebk - bk:
                    db.session.delete(existing_buckets[resource_id].resource)
                    self.log.debug('Deleted S3Bucket {}/{}'.format(
                        self.account.account_name,
                        resource_id
                    ))
                db.session.commit()
            except:
                db.session.rollback()
        finally:
            del s3

    @retry
    def update_cloudfront(self):
        """Update list of CloudFront Distributions for the account

        Returns:
            `None`
        """
        self.log.debug('Updating CloudFront distributions for {}'.format(self.account.account_name))
        cfr = self.session.client('cloudfront')

        try:
            existing_dists = CloudFrontDist.get_all(self.account, None)
            dists = []

            #region Fetch information from API
            #region Web distributions
            done = False
            marker = None
            while not done:
                if marker:
                    response = cfr.list_distributions(Marker=marker)
                else:
                    response = cfr.list_distributions()

                dl = response['DistributionList']
                if dl['IsTruncated']:
                    marker = dl['NextMarker']
                else:
                    done = True

                if 'Items' in dl:
                    for dist in dl['Items']:
                        origins = []
                        for origin in dist['Origins']['Items']:
                            if 'S3OriginConfig' in origin:
                                origins.append(
                                    {
                                        'type': 's3',
                                        'source': origin['DomainName']
                                    }
                                )
                            elif 'CustomOriginConfig' in origin:
                                origins.append(
                                    {
                                        'type': 'custom-http',
                                        'source': origin['DomainName']
                                    }
                                )

                        data = {
                            'arn': dist['ARN'],
                            'name': dist['DomainName'],
                            'origins': origins,
                            'enabled': dist['Enabled'],
                            'type': 'web',
                            'tags': self.__get_distribution_tags(cfr, dist['ARN'])
                        }
                        dists.append(data)
            #endregion

            #region Streaming distributions
            done = False
            marker = None
            while not done:
                if marker:
                    response = cfr.list_streaming_distributions(Marker=marker)
                else:
                    response = cfr.list_streaming_distributions()

                dl = response['StreamingDistributionList']
                if dl['IsTruncated']:
                    marker = dl['NextMarker']
                else:
                    done = True

                if 'Items' in dl:
                    dists += [
                        {
                            'arn': x['ARN'],
                            'name': x['DomainName'],
                            'origins': [{'type': 's3', 'source': x['S3Origin']['DomainName']}],
                            'enabled': x['Enabled'],
                            'type': 'rtmp',
                            'tags': self.__get_distribution_tags(cfr, x['ARN'])
                        } for x in dl['Items']
                    ]
            #endregion
            # endregion

            for data in dists:
                if data['arn'] in existing_dists:
                    dist = existing_dists[data['arn']]
                    if dist.update(data):
                        self.log.debug('Updated CloudFrontDist {}/{}'.format(
                            self.account.account_name,
                            data['name']
                        ))
                        dist.save()

                else:
                    properties = {
                        'domain_name': data['name'],
                        'origins': data['origins'],
                        'enabled': data['enabled'],
                        'type': data['type']
                    }

                    CloudFrontDist.create(
                        data['arn'],
                        account_id=self.account.account_id,
                        properties=properties,
                        tags=data['tags']
                    )

                    self.log.debug('Added new CloudFrontDist {}/{}'.format(
                        self.account.account_name,
                        data['name']
                    ))
            db.session.commit()

            dk = set(x['arn'] for x in dists)
            edk = set(existing_dists.keys())

            try:
                for resource_id in edk - dk:
                    db.session.delete(existing_dists[resource_id].resource)
                    self.log.debug('Deleted CloudFrontDist {}/{}'.format(
                        resource_id,
                        self.account.account_name
                    ))
                db.session.commit()
            except:
                db.session.rollback()
        finally:
            del cfr

    @retry
    def update_route53(self):
        """Update list of Route53 DNS Zones and their records for the account

        Returns:
            `None`
        """
        self.log.debug('Updating Route53 information for {}'.format(self.account))

        # region Update zones
        existing_zones = DNSZone.get_all(self.account)
        zones = self.__fetch_route53_zones()
        for resource_id, data in zones.items():
            if resource_id in existing_zones:
                zone = DNSZone.get(resource_id)
                if zone.update(data):
                    self.log.debug('Change detected for Route53 zone {}/{}'.format(
                        self.account,
                        zone.name
                    ))
                    zone.save()
            else:
                tags = data.pop('tags')
                DNSZone.create(
                    resource_id,
                    account_id=self.account.account_id,
                    properties=data,
                    tags=tags
                )

                self.log.debug('Added Route53 zone {}/{}'.format(
                    self.account,
                    data['name']
                ))

        db.session.commit()

        zk = set(zones.keys())
        ezk = set(existing_zones.keys())

        for resource_id in ezk - zk:
            zone = existing_zones[resource_id]

            db.session.delete(zone.resource)
            self.log.debug('Deleted Route53 zone {}/{}'.format(
                self.account.account_name,
                zone.name.value
            ))
        db.session.commit()
        # endregion

        # region Update resource records
        try:
            for zone_id, zone in DNSZone.get_all(self.account).items():
                existing_records = {rec.id: rec for rec in zone.records}
                records = self.__fetch_route53_zone_records(zone.get_property('zone_id').value)

                for data in records:
                    if data['id'] in existing_records:
                        record = existing_records[data['id']]
                        if record.update(data):
                            self.log.debug('Changed detected for DNSRecord {}/{}/{}'.format(
                                self.account,
                                zone.name,
                                data['name']
                            ))
                            record.save()
                    else:
                        record = DNSRecord.create(
                            data['id'],
                            account_id=self.account.account_id,
                            properties={k: v for k, v in data.items() if k != 'id'},
                            tags={}
                        )
                        self.log.debug('Added new DNSRecord {}/{}/{}'.format(
                            self.account,
                            zone.name,
                            data['name']
                        ))
                        zone.add_record(record)
                db.session.commit()

                rk = set(x['id'] for x in records)
                erk = set(existing_records.keys())

                for resource_id in erk - rk:
                    record = existing_records[resource_id]
                    zone.delete_record(record)
                    self.log.debug('Deleted Route53 record {}/{}/{}'.format(
                        self.account.account_name,
                        zone_id,
                        record.name
                    ))
                db.session.commit()
        except:
            raise
        # endregion

    # region Helper functions
    @retry
    def __get_distribution_tags(self, client, arn):
        """Returns a dict containing the tags for a CloudFront distribution

        Args:
            client (botocore.client.CloudFront): Boto3 CloudFront client object
            arn (str): ARN of the distribution to get tags for

        Returns:
            `dict`
        """
        return {
            t['Key']: t['Value'] for t in client.list_tags_for_resource(
                Resource=arn
            )['Tags']['Items']
        }

    @retry
    def __fetch_route53_zones(self):
        """Return a list of all DNS zones hosted in Route53

        Returns:
            :obj:`list` of `dict`
        """
        done = False
        marker = None
        zones = {}
        route53 = self.session.client('route53')

        try:
            while not done:
                if marker:
                    response = route53.list_hosted_zones(Marker=marker)
                else:
                    response = route53.list_hosted_zones()

                if response['IsTruncated']:
                    marker = response['NextMarker']
                else:
                    done = True

                for zone_data in response['HostedZones']:
                    zones[get_resource_id('r53z', zone_data['Id'])] = {
                        'name': zone_data['Name'],
                        'source': 'AWS/{}'.format(self.account),
                        'comment': zone_data['Config']['Comment'] if 'Comment' in zone_data['Config'] else None,
                        'zone_id': zone_data['Id'],
                        'private_zone': zone_data['Config']['PrivateZone'],
                        'tags': self.__fetch_route53_zone_tags(zone_data['Id'])
                    }

            return zones
        finally:
            del route53

    @retry
    def __fetch_route53_zone_records(self, zone_id):
        """Return all resource records for a specific Route53 zone

        Args:
            zone_id (`str`): Name / ID of the hosted zone

        Returns:
            `dict`
        """
        route53 = self.session.client('route53')

        done = False
        nextName = nextType = None
        records = {}

        try:
            while not done:
                if nextName and nextType:
                    response = route53.list_resource_record_sets(
                        HostedZoneId=zone_id,
                        StartRecordName=nextName,
                        StartRecordType=nextType
                    )
                else:
                    response = route53.list_resource_record_sets(HostedZoneId=zone_id)

                if response['IsTruncated']:
                    nextName = response['NextRecordName']
                    nextType = response['NextRecordType']
                else:
                    done = True

                if 'ResourceRecordSets' in response:
                    for record in response['ResourceRecordSets']:
                        # Cannot make this a list, due to a race-condition in the AWS api that might return the same
                        # record more than once, so we use a dict instead to ensure that if we get duplicate records
                        # we simply just overwrite the one already there with the same info.
                        record_id = self._get_resource_hash(zone_id, record)
                        if 'AliasTarget' in record:
                            value = record['AliasTarget']['DNSName']
                            records[record_id] = {
                                'id': record_id,
                                'name': record['Name'],
                                'type': 'ALIAS',
                                'ttl': 0,
                                'value': [value]
                            }
                        else:
                            value = [y['Value'] for y in record['ResourceRecords']]
                            records[record_id] = {
                                'id': record_id,
                                'name': record['Name'],
                                'type': record['Type'],
                                'ttl': record['TTL'],
                                'value': value
                            }

            return list(records.values())
        finally:
            del route53

    @retry
    def __fetch_route53_zone_tags(self, zone_id):
        """Return a dict with the tags for the zone

        Args:
            zone_id (`str`): ID of the hosted zone

        Returns:
            :obj:`dict` of `str`: `str`
        """
        route53 = self.session.client('route53')

        try:
            return {
                tag['Key']: tag['Value'] for tag in
                    route53.list_tags_for_resource(
                        ResourceType='hostedzone',
                        ResourceId=zone_id.split('/')[-1]
                    )['ResourceTagSet']['Tags']
            }
        finally:
            del route53

    @staticmethod
    def _get_resource_hash(zone_name, record):
        """Returns the last ten digits of the sha256 hash of the combined arguments. Useful for generating unique
        resource IDs

        Args:
            zone_name (`str`): The name of the DNS Zone the record belongs to
            record (`dict`): A record dict to generate the hash from

        Returns:
            `str`
        """
        record = defaultdict(int, record)
        args = [
            zone_name,
            record['Name'],
            record['Type'],
            record['Weight'],
            record['Region'],
            record['GeoLocation'],
            record['Failover'],
            record['HealthCheckId'],
            record['TrafficPolicyInstanceId']
        ]

        return get_resource_id('r53r', args)
    # endregion
