# -*- coding: utf-8 -*-
#
# (C) Copyright Connected Digital Economy Catapult Limited 2014
# All rights reserved
#
import os
import logging

from flask import (
    Flask, request, make_response, jsonify, session)
from flask.ext.session import Session
from rdflib.plugins.parsers.notation3 import BadSyntax

from triples import (
    generate_d3_directed_graph, UnknownEntityType, UnknownContextType,
    DocumentError)

format = '%(asctime)s - %(levelname)s - %(message)s'
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(format))
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(ch)

app = Flask(__name__)
SESSION_TYPE = 'filesystem'
app.secret_key = ('>\x05h\xddA\\p\xd1\xc2\xbd\x1cad'
                  '\xa2\x19R\xa9<\xc0\xe64\xce\xf7\x8c')
app.config.from_object(__name__)
Session(app)


@app.route('/')
def index():
    default_doc = os.path.join(app.static_folder, 'sampledata/sample1.ttl')
    session['doc'] = open(default_doc, 'r').read()
    return app.send_static_file('index.html')


@app.route('/render', methods=['POST'])
def render():
    try:
        triples = request.files['triples'].read()
        minimize = request.form.get('min', 'false') == 'true'
        session['doc'] = triples
        return generate_graph(session['doc'], minimize)
    except Exception as exc:
        logger.exception('unexpected error', exc)
        return make_response(
            jsonify(error='unexpected error'), 400)


def generate_graph(doc, minimize):
    try:
        return generate_d3_directed_graph(doc, minimize)
    except BadSyntax as exc:
        error = unicode(exc).encode('utf-8')
        return make_response(jsonify(error=error), 400)
    except (UnknownEntityType, UnknownContextType, DocumentError) as exc:
        return make_response(jsonify(error=unicode(exc).encode('utf-8')), 400)
    except Exception as exc:
        logger.exception('unexpected error')
        return make_response(
            jsonify(error='Conversion failed. something wrong with the file?'),
            400)


@app.route('/expand', methods=['GET'])
def expand():
    return generate_graph(session['doc'], False)


@app.route('/compress', methods=['GET'])
def compress():
    return generate_graph(session['doc'], True)


if __name__ == '__main__':
    app.run()
