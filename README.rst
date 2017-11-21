******************
cinq-collector-aws
******************

The base AWS collector queries all regions for every account collecting information for the following:

=======
Account
=======

Update the list of resources that are account wide

* S3 Buckets
* CloudFront Distributions
* Route53 DNS Zones and records

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

=====================
Configuration Options
=====================


===========    =============   ====   ======
Option name    Default Value   Type   Description
===========    =============   ====   ======
enabled        True            bool   Enable the AWS collector
===========    =============   ====   ======
