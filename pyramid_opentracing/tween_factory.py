import importlib
from pyramid.settings import asbool, aslist
from pyramid.tweens import INGRESS

import opentracing

from .tracing import PyramidTracing


DEFAULT_TWEEN_TRACE_ALL = True


def _get_function_from_name(full_name):
    mod_name, func_name = full_name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name, None)


def _call_base_tracer_func(full_name, settings):
    return _get_function_from_name(full_name)(**settings)


def opentracing_tween_factory(handler, registry):
    """
    The factory method is called once, and we thus retrieve the settings as
    defined on the global configuration.
    We set the 'opentracing_tracer' in the settings too, for further reference
    and usage.
    """
    base_tracer = registry.settings.get('ot.base_tracer', opentracing.Tracer())
    traced_attrs = aslist(registry.settings.get('ot.traced_attributes', []))
    trace_all = asbool(registry.settings.get('ot.trace_all',
                                             DEFAULT_TWEEN_TRACE_ALL))
    operation_name_func = None

    if 'ot.base_tracer_func' in registry.settings:
        base_tracer_func = registry.settings.get('ot.base_tracer_func')
        base_tracer = _call_base_tracer_func(base_tracer_func,
                                             registry.settings)

    if 'ot.operation_name_func' in registry.settings:
        operation_name_func = registry.settings.get('ot.operation_name_func')
        if not callable(operation_name_func):
            operation_name_func = _get_function_from_name(operation_name_func)

    tracing = PyramidTracing(base_tracer, trace_all, operation_name_func)
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
