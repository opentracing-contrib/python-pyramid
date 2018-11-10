import importlib
from pyramid.settings import asbool, aslist
from pyramid.tweens import INGRESS

from .tracing import PyramidTracing


DEFAULT_TWEEN_TRACE_ALL = True


def _get_callable_from_name(full_name):
    mod_name, func_name = full_name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name, None)


def _get_deprecated_base_tracer(registry):
    base_tracer = registry.settings.get('ot.base_tracer', None)
    if base_tracer is not None:
        return base_tracer

    base_tracer_func = registry.settings.get('ot.base_tracer_func', None)
    if base_tracer_func is None:  # Nothing to do here.
        return None

    if not callable(base_tracer_func):
        base_tracer_func = _get_callable_from_name(base_tracer_func)

    return base_tracer_func(**registry.settings)


def opentracing_tween_factory(handler, registry):
    """
    The factory method is called once, and we thus retrieve the settings as
    defined on the global configuration.
    We set  'ot.tracing' in the settings too in case the user didnt set
    it himself, for further usage.
    """
    tracing = registry.settings.get('ot.tracing', None)
    traced_attrs = aslist(registry.settings.get('ot.traced_attributes', []))
    trace_all = asbool(registry.settings.get('ot.trace_all',
                                             DEFAULT_TWEEN_TRACE_ALL))
    start_span_cb = registry.settings.get('ot.start_span_cb', None)

    if start_span_cb is not None and not callable(start_span_cb):
        start_span_cb = _get_callable_from_name(start_span_cb)

    if 'ot.tracing_callable' in registry.settings:
        tracing_callable = registry.settings.get('ot.tracing_callable')
        if not callable(tracing_callable):
            tracing_callable = _get_callable_from_name(tracing_callable)

        tracing = tracing_callable(**registry.settings)

    if 'ot.tracer_callable' in registry.settings:
        tracer_callable = registry.settings.get('ot.tracer_callable')
        tracer_params = registry.settings.get('ot.tracer_parameters', {})
        if not callable(tracer_callable):
            tracer_callable = _get_callable_from_name(tracer_callable)

        tracer = tracer_callable(**tracer_params)
        tracing = PyramidTracing(tracer)

    # Try to use the deprecated names.
    base_tracer = _get_deprecated_base_tracer(registry)
    if base_tracer is not None:
        tracing = PyramidTracing(base_tracer)

    if tracing is None:  # Fallback to the global tracer.
        tracing = PyramidTracing()

    tracing._start_span_cb = start_span_cb
    tracing._trace_all = trace_all
    registry.settings['ot.tracing'] = tracing

    def opentracing_tween(req):
        # if tracing for all requests is disabled, continue with the
        # normal handlers flow and return immediately.
        if not tracing._trace_all:
            return handler(req)

        tracing._apply_tracing(req, traced_attrs)
        try:
            res = handler(req)
        except Exception as e:
            tracing._finish_tracing(req, error=e)
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
