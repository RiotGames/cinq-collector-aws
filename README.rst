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

Update the list of the following resources for a specific account and region

* EC2 Instances
* AMIs
* EBS Volumes
* EBS Snapshots
* Elastic BeanStalks

Please check out the `README <https://github.com/RiotGames/cloud-inquisitor/blob/master/docs/backend/README.rst>`_ 
for further details on the how ``cinq-collector-aws`` works with further details on ``Cloud Inquisitor`` backend is built and what technologies we use.
