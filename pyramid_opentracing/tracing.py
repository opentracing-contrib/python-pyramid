import opentracing
from opentracing.ext import tags

from ._constants import SCOPE_ATTR


# Ported from the Django library:
# https://github.com/opentracing-contrib/python-django
class PyramidTracing(object):
    """
    @param tracer the OpenTracing tracer to be used
    to trace requests using this PyramidTracing
    """
    def __init__(self, tracer=None, start_span_cb=None):
        if start_span_cb is not None and not callable(start_span_cb):
            raise ValueError('start_span_cb is not callable')

        self._tracer_obj = tracer
        self._start_span_cb = start_span_cb
        self._trace_all = False

    @property
    def _tracer(self):
        """
        DEPRECATED
        """
        return self.tracer

    @property
    def tracer(self):
        """
        ADD docs here.
        """
        if self._tracer_obj is None:
            return opentracing.tracer

        return self._tracer_obj

    def get_span(self, request):
        """
        @param request
        Returns the span tracing this request
        """
        scope = getattr(request, SCOPE_ATTR, None)
        return None if scope is None else scope.span

    def trace(self, *attributes):
        """
        Function decorator that traces functions
        NOTE: Must be placed after the @view_config decorator
        @param attributes any number of pyramid.request.Request attributes
        (strings) to be set as tags on the created span
        """
        def decorator(view_func):
            def wrapper(request):
                if self._trace_all:
                    return view_func(request)

                self._apply_tracing(request, list(attributes))
                try:
                    r = view_func(request)
                except Exception as e:
                    self._finish_tracing(request, error=e)
                    raise

                self._finish_tracing(request)
                return r

            return wrapper
        return decorator

    def _get_operation_name(self, request):
        if getattr(request, 'matched_route', None) is None:
            return request.method

        return request.matched_route.name

    def _apply_tracing(self, request, attributes):
        """
        Helper function to avoid rewriting for middleware and decorator.
        Returns a new span from the request with logged attributes and
        correct operation name from the view_func.
        """
        headers = request.headers
        operation_name = self._get_operation_name(request)

        # start new span from trace info
        try:
            span_ctx = self._tracer.extract(opentracing.Format.HTTP_HEADERS,
                                            headers)
            scope = self._tracer.start_active_span(operation_name,
                                                   child_of=span_ctx)
        except (opentracing.InvalidCarrierException,
                opentracing.SpanContextCorruptedException):
            scope = self._tracer.start_active_span(operation_name)

        # add span to current spans
        setattr(request, SCOPE_ATTR, scope)

        # Standard tags.
        scope.span.set_tag(tags.COMPONENT, 'pyramid')
        scope.span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_SERVER)
        scope.span.set_tag(tags.HTTP_METHOD, request.method)
        scope.span.set_tag(tags.HTTP_URL, request.path_url)

        # log any traced attributes
        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    scope.span.set_tag(attr, payload)

        # invoke the start span callback, if any
        self._call_start_span_cb(scope.span, request)

        return scope.span

    def _finish_tracing(self, request, error=None):
        scope = getattr(request, SCOPE_ATTR, None)
        if scope is None:
            return

        delattr(request, SCOPE_ATTR)

        if error is not None:
            scope.span.set_tag(tags.ERROR, True)
            scope.span.log_kv({
                'event': tags.ERROR,
                'error.object': error,
            })
        else:
            scope.span.set_tag(tags.HTTP_STATUS_CODE,
                               request.response.status_code)

        if getattr(request, 'matched_route', None) is not None:
            scope.span.set_tag('pyramid.route', request.matched_route.name)

        scope.close()

    def _call_start_span_cb(self, span, request):
        if self._start_span_cb is None:
            return

        try:
            self._start_span_cb(span, request)
        except Exception:
            # TODO - log the error to the Span?
            pass
