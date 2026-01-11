defaults = {
    'coredns': {
        'version': '1.13.2',
        'snippets': {
            # 'internalView': [
            #     'view internal {',
            #         "expr (incidr(client_ip(), '127.1.0.0/24'))",
            #     '}',
            # ],
        },
        'servers': {
            # 'internal': {
            #     'domain': '.',
            #     'port': '5302',
            #     'auto': {
            #         'enabled': True,
            #         'dir': '/etc/coredns/zones/internal',
            #         'reload': '10s',
            #     },
            #     'notify': [
            #
            #     ],
            #     'config': [
            #         'import internalView',
            #         'errors',
            #     ],
            #     'zones': {
            #         'home.andreflemming.de': {
            #             'zone_type': 'group',
            #             'group': 'home',
            #             'interfaces': {
            #                 'eth0': {
            #                     'cname': True,
            #                 },
            #             },
            #             'records': {
            #                 'foo': [
            #                     {
            #                         'type': 'A',
            #                         'value': '127.0.0.1',
            #                     },
            #                 ],
            #             },
            #         },
            #     },
            # },
        },
    },
}
