##############################################################################
# COPYRIGHT Ericsson AB 2021
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################
from naslib.connection import NasConnection

import argparse
import pprint
import logging

def main():
    parser = argparse.ArgumentParser(description='cli for nassfs')
    parser.add_argument(
        '--action',
        choices=[
            'fslist',
            'fscreate',
            'fsdelete',
            'fsresize',
            'sharelist',
            'sharecreate',
            'sharedelete',
            'snaplist',
            'snapcreate',
            'snapdelete',
            'snaprestore'
        ],
        required=True
    )
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument(
        '--nas_type',
        choices=['veritas', 'unityxt'],
        required=True
    )

    parser.add_argument('--name')
    parser.add_argument('--size')
    parser.add_argument('--pool')
    parser.add_argument('--layout')
    parser.add_argument('--path')
    parser.add_argument('--client')
    parser.add_argument('--options')

    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args()

    logging_level = logging.WARN
    if args.debug:
        logging_level = logging.DEBUG
    logging.basicConfig(level=logging_level)

    with NasConnection(
        host=args.host,
        username=args.username,
        password=args.password,
        nas_type=args.nas_type
    ) as nfs:
        if args.action == 'fslist':
            for fs in nfs.filesystem.list():
                pprint.pprint(fs)
        elif args.action == 'fscreate':
            fs = nfs.filesystem.create(
                name=args.name,
                size=args.size,
                pool=args.pool,
                layout=args.layout
            )
            pprint.pprint(fs)
        elif args.action == 'fsdelete':
            fs = nfs.filesystem.delete(
                name=args.name
            )
        elif args.action == 'fsresize':
            fs = nfs.filesystem.resize(
                name=args.name,
                size=args.size
            )
        elif args.action == 'sharelist':
            for share in nfs.share.list():
                pprint.pprint(share)
        elif args.action == 'sharecreate':
            share = nfs.share.create(
                path=args.path,
                client=args.client,
                options=args.options
            )
            pprint.pprint(share)
        elif args.action == 'sharedelete':
            nfs.share.delete(
                path=args.path,
                client=args.client
            )
        elif args.action == 'snaplist':
            for snap in nfs.snapshot.list():
                pprint.pprint(snap)
        elif args.action == 'snapcreate':
            snap = nfs.snapshot.create(
                name=args.name,
                filesystem=args.path.split('/')[-1],
                cache=None
            )
            pprint.pprint(snap)
        elif args.action == 'snapdelete':
            nfs.snapshot.delete(
                name=args.name,
                filesystem=args.path.split('/')[-1],
            )
        elif args.action == 'snaprestore':
            nfs.snapshot.restore(
                name=args.name,
                filesystem=args.path.split('/')[-1],
            )


if __name__ == "__main__":
    main()
