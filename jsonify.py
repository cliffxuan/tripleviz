#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
script to jsonfiy a lcc document
"""
import argparse
import json
from collections import OrderedDict

from repository.models import entity_model

SUPPORTED_FORMATS = ['turtle', 'xml', 'nt', 'json-ld']


def sort(item):
    if isinstance(item, dict):
        return OrderedDict(sorted((k, sort(v)) for k, v in item.items()))
    elif isinstance(item, (list, tuple)):
        return sorted(item)
    return item


def argument_parser():
    parser = argparse.ArgumentParser(
        description='describe me')
    parser.add_argument(
        'filename', type=argparse.FileType('r'),
        help='name of the file to convert')
    parser.add_argument(
        'source_format', default='turtle', nargs='?',
        choices=SUPPORTED_FORMATS,
        help='source format')
    return parser


def main(argv=None):
    args = argument_parser().parse_args(argv)
    graph = entity_model.Graph()
    graph.parse(args.filename, format=args.source_format)
    result = {entity_model.shorten(right.id): json.loads(right.jsonify())
              for right in graph.iter_right()}
    result = sort(result)
    print json.dumps(result, indent=2)


if __name__ == '__main__':
    main()
