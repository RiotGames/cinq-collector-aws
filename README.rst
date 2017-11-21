******************
cinq-collector-aws
******************

The base AWS collector queries all regions for every account collecting information for the following:

=======
Account
=======

* S3 Buckets for the account
* CloudFront Distributions for the account
* Route53 DNS Zones and their records for the account
* DNS zones hosted in Route53
* All resource records for a specific Route53 zone
* Tags for the zone (returned as a dict)

=======
Region
=======

* Update list of EC2 Instances for the account / region
* Update list of AMIs for the account / region
* Update list of EBS Volumes for the account / region
* Update list of EBS Snapshots for the account / region
* Update list of Elastic BeanStalks for the account / region

Please check out the `README <https://github.com/RiotGames/cloud-inquisitor/blob/master/docs/backend/README.rst>`_ 
for further details on the how ``cinq-collector-aws`` works with further detauks on ``Cloud Inquisitor`` backend is built and what technologies we use.
