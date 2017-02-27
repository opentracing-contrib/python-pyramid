from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.view import view_config

import opentracing
from pyramid_opentracing import PyramidTracer

# Pass a specific Tracer instance to PyramidTracer()
tracer = PyramidTracer(opentracing.Tracer())

@view_config(route_name='root', renderer='json')
def server_index(request):
    return { 'message': 'Hello world!' }

@tracer.trace('method')
@view_config(route_name='simple', renderer='json')
def server_simple(request):
    return { 'message': 'This is a simple traced request.' }

@tracer.trace()
@view_config(route_name='log', renderer='json')
def server_log(request):
    if tracer.get_span(request) is not None:
        span.log_event('Hello, World!')
    return { 'message': 'Something was logged' }

@tracer.trace()
@view_config(route_name='childspan', renderer='json')
def server_child_span(request):
    if tracer.get_span(request) is not None:
        child_span = tracer._tracer.start_span('child_span', child_of=span.context)
        child_span.finish()
    return { 'message': 'A child span was created' }


if __name__ == '__main__':
    config = Configurator()
    config.add_route('root', '/')
    config.add_route('simple', '/simple')
    config.add_route('log', '/log')
    config.add_route('childspan', '/childspan')
    config.scan()

    app = config.make_wsgi_app()
    server = make_server('127.0.0.1', 8080, app)
    server.serve_forever()

