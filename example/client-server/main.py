import urllib2

from pyramid.view import view_config
from pyramid.config import Configurator

import opentracing
import pyramid_opentracing
from waitress import serve


tracing = pyramid_opentracing.PyramidTracing(opentracing.Tracer())


# Client
@view_config(route_name='client_simple', renderer='json')
@tracing.trace()
def client_simple(request):
    url = 'http://127.0.0.1:8080/server/simple'
    new_request = urllib2.Request(url)
    current_span = tracing.get_span(request)
    inject_as_headers(tracing, current_span, new_request)
    try:
        urllib2.urlopen(new_request)
        return {'message': 'Made a simple request'}
    except urllib2.URLError as e:
        return {'error': e}


@view_config(route_name='client_log', renderer='json')
@tracing.trace()
def client_log(request):
    url = 'http://127.0.0.1:8080/server/log'
    new_request = urllib2.Request(url)
    current_span = tracing.get_span(request)
    inject_as_headers(tracing, current_span, new_request)
    try:
        urllib2.urlopen(new_request)
        return {'message': 'Sent a request to log'}
    except urllib2.URLError as e:
        return {'error': e}


@view_config(route_name='client_child_span', renderer='json')
@tracing.trace()
def client_child_span(request):
    url = 'http://127.0.0.1:8080/server/childspan'
    new_request = urllib2.Request(url)
    current_span = tracing.get_span(request)
    inject_as_headers(tracing, current_span, new_request)
    try:
        urllib2.urlopen(new_request)
        return {'message': 'Sent a request that should produce an additional child span'}
    except urllib2.URLError as e:
        return {'error': e}


def inject_as_headers(tracing, span, request):
    text_carrier = {}
    tracing._tracer.inject(span.context,
                           opentracing.Format.TEXT_MAP,
                           text_carrier)

    for k, v in text_carrier.iteritems():
        request.add_header(k, v)


# Server
@view_config(route_name='server_simple', renderer='json')
@tracing.trace('method')
def server_simple(request):
    return {'message': 'This is a simple traced request'}


@view_config(route_name='server_log', renderer='json')
@tracing.trace()
def server_log(request):
    span = tracing.get_span(request)
    span.log_event('Hello, world!')
    return {'message': 'Something was logged'}


@view_config(route_name='server_child_span', renderer='json')
@tracing.trace()
def server_child_span(request):
    span = tracing.get_span(request)
    child_span = tracing._tracer.start_span('child_span',
                                            child_of=span.context)
    child_span.finish()
    return {'message': 'A child span was created'}


if __name__ == '__main__':
    config = Configurator()
    config.add_route('client_simple', '/client/simple')
    config.add_route('client_log', '/client/log')
    config.add_route('client_child_span', '/client/childspan')
    config.add_route('server_simple', '/server/simple')
    config.add_route('server_log', '/server/log')
    config.add_route('server_child_span', '/server/childspan')
    config.scan()
    client_app = config.make_wsgi_app()

    serve(client_app, host='127.0.0.1', port=8080)
