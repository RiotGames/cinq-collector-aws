'''views for cinq_collector_elb'''

from cloud_inquisitor.constants import ROLE_USER, HTTP
from cloud_inquisitor.plugins import BaseView
from cloud_inquisitor.utils import MenuItem
from cloud_inquisitor.wrappers import check_auth, rollback
from cinq_collector_aws.resources import ELB


class ELBList(BaseView):
    URLS = ['/api/v1/elb']
    MENU_ITEMS = [
        MenuItem(
            'browse',
            'ELBs',
            'elb.list',
            'elb',
            args={
                'page': 1,
                'count': 100,
                'accounts': None,
                'regions': None,
                'num_instances': None
            },
            order=4
        )
    ]

    @rollback
    @check_auth(ROLE_USER)
    def get(self):
        self.reqparse.add_argument('page', type=int, default=1)
        self.reqparse.add_argument('count', type=int, default=100, choices=[25, 50, 100])
        self.reqparse.add_argument('accounts', type=str, default=None, action='append')
        self.reqparse.add_argument('regions', type=str, default=None, action='append')
        self.reqparse.add_argument('numInstances', type=int, default=None)

        args = self.reqparse.parse_args()
        query = {
            'limit': args['count'],
            'page': args['page'],
            'properties': {}
        }
        if args['accounts']:
            query['accounts'] = args['accounts']
        if args['regions']:
            query['locations'] = args['regions']
        # Javascript camelCase to Python snake_case
        if args['numInstances'] is not None:
            self.log.info('args has numInstances=%s', args['numInstances'])
            query.setdefault('properties', {})['num_instances'] = args['numInstances']

        if (args['page'] - 1) > 0:
            query['page'] = args['page']

        total, elbs = ELB.search(**query)
        elbs = [x.to_json() for x in elbs]
        elb_count = len(elbs)

        response = {
            'message': None,
            'elbCount': total,
            'elbs': elbs
        }
        if elb_count == 0:
            return self.make_response(
                {
                    'message': 'No ELBS found matching criteria',
                    'elbCount': total,
                    'elbs': []
                },
                HTTP.NOT_FOUND
            )
        return self.make_response(response)


class ELBGet(BaseView):
    URLS = ['/api/v1/elb/<string:elb_name>']

    @rollback
    @check_auth(ROLE_USER)
    def get(self, elb_name):
        elb = ELB.get(elb_name)
        return self.make_response(
            {
                'elb': elb
            },
            HTTP.OK
        )
