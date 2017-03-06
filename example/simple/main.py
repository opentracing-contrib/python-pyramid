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

@view_config(route_name='simple', renderer='json')
@tracer.trace('method')
def server_simple(request):
    return { 'message': 'This is a simple traced request.' }

@view_config(route_name='log', renderer='json')
@tracer.trace()
def server_log(request):
    if tracer.get_span(request) is not None:
        span.log_event('Hello, World!')
    return { 'message': 'Something was logged' }

if __name__ == '__main__':
    config = Configurator()
    config.add_route('root', '/')
    config.add_route('simple', '/simple')
    config.add_route('log', '/log')
    config.scan()

    app = config.make_wsgi_app()
    server = make_server('127.0.0.1', 8080, app)
    server.serve_forever()

