from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.view import view_config

import lightstep
import opentracing

# Replace it with another opentracing implementation if desired
base_tracer = lightstep.Tracer(component_name='pyramid_app', access_token='{your_lightstep_token}')

@view_config(route_name='root', renderer='json')
def server_index(request):
    return { 'message': 'Hello world!' }

@view_config(route_name='simple', renderer='json')
def server_simple(request):
    return { 'message': 'This is a simple traced request.' }

@view_config(route_name='log', renderer='json')
def server_log(request):
    return { 'message': 'Something was logged' }


if __name__ == '__main__':
    config = Configurator()
    config.add_route('root', '')
    config.add_route('simple', '/simple')
    config.add_route('log', '/log')
    config.scan()

    # Tween setup
    config.add_settings(opentracing_traced_attributes=['host', 'method'])
    config.add_settings(opentracing_trace_all=True)
    config.add_settings(opentracing_base_tracer=base_tracer)
    config.include('pyramid_opentracing')

    app = config.make_wsgi_app()
    server = make_server('127.0.0.1', 8080, app)
    server.serve_forever()

