import opentracing

from .tracer import PyramidTracer

def opentracing_tween_factory(handler, registry):
    '''
    The factory method is called once, and we thus retrieve the settings as defined
    on the global configuration.
    We set the 'opentracing_tracer' in the settings to, for further reference and usage.
    '''
    base_tracer = registry.settings.get('ot.base_tracer', opentracing.Tracer())
    traced_attrs = registry.settings.get('ot.traced_attributes', [])
    trace_all = registry.settings.get('ot.trace_all', False)

    tracer = PyramidTracer(base_tracer, trace_all)
    registry.settings ['ot.tracer'] = tracer

    def opentracing_tween(req):
        # if tracing for all requests is disabled, continue with the
        # normal handlers flow and return immediately.
        if not trace_all:
            return handler(req)

        span = tracer._apply_tracing(req, traced_attrs)
        res = handler(req)
        tracer._finish_tracing(req)

        return res

    return opentracing_tween

def includeme(config):
    '''
    Set up an implicit 'tween' to do tracing on all the requests, with
    optionally including fields on the request object (method, url, path, etc).
    '''
    config.add_tween('pyramid_opentracing.opentracing_tween_factory')

