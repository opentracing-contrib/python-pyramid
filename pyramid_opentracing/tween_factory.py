import opentracing

from .tracer import PyramidTracer

def opentracing_tween_factory(handler, registry):
    base_tracer = registry.settings.get('opentracing_base_tracer', opentracing.Tracer())
    traced_attrs = registry.settings.get('opentracing_traced_attributes', [])
    trace_all = registry.settings.get('opentracing_trace_all', False)

    tracer = PyramidTracer(base_tracer, trace_all)
    registry.settings ['opentracing_tracer'] = tracer

    def opentracing_tween(req):
        if not trace_all:
            return handler(req)

        span = tracer._apply_tracing(req, traced_attrs)
        res = handler(req)
        tracer._finish_tracing(req)

        return res

    return opentracing_tween

def includeme(config):
    config.add_tween('pyramid_opentracing.opentracing_tween_factory')

