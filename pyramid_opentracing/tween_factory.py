import importlib
from pyramid.settings import asbool, aslist
from pyramid.tweens import INGRESS

from .tracing import PyramidTracing


DEFAULT_TWEEN_TRACE_ALL = True


def _get_callable_from_name(full_name):
    mod_name, func_name = full_name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name, None)


def _call_tracer_callable(full_name, settings):
    return _get_callable_from_name(full_name)(**settings)


def opentracing_tween_factory(handler, registry):
    """
    The factory method is called once, and we thus retrieve the settings as
    defined on the global configuration.
    We set the 'opentracing_tracer' in the settings too, for further reference
    and usage.
    """
    tracer = registry.settings.get('ot.tracer', None)
    traced_attrs = aslist(registry.settings.get('ot.traced_attributes', []))
    trace_all = asbool(registry.settings.get('ot.trace_all',
                                             DEFAULT_TWEEN_TRACE_ALL))
    start_span_cb = None

    if 'ot.tracer_callable' in registry.settings:
        tracer_callable = registry.settings.get('ot.tracer_callable')
        tracer = _call_tracer_callable(tracer_callable,
                                       registry.settings)

    if 'ot.start_span_cb' in registry.settings:
        start_span_cb = registry.settings.get('ot.start_span_cb')
        if not callable(start_span_cb):
            start_span_cb = _get_callable_from_name(start_span_cb)

    tracing = PyramidTracing(tracer, trace_all, start_span_cb)
    registry.settings['ot.tracing'] = tracing

    def opentracing_tween(req):
        # if tracing for all requests is disabled, continue with the
        # normal handlers flow and return immediately.
        if not trace_all:
            return handler(req)

        tracing._apply_tracing(req, traced_attrs)
        try:
            res = handler(req)
        except:
            tracing._finish_tracing(req, error=True)
            raise

        tracing._finish_tracing(req)
        return res

    return opentracing_tween


def includeme(config):
    """
    Set up an implicit 'tween' to do tracing on all the requests, with
    optionally including fields on the request object (method, url, path, etc).
    """
    config.add_tween('pyramid_opentracing.opentracing_tween_factory',
                     under=INGRESS)
