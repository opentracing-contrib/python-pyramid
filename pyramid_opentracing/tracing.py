import opentracing
from opentracing.ext import tags


# Ported from the Django library:
# https://github.com/opentracing-contrib/python-django
class PyramidTracing(object):
    """
    @param tracer the OpenTracing tracer to be used
    to trace requests using this PyramidTracing
    """
    def __init__(self, tracer=None, trace_all=False, start_span_cb=None):
        if start_span_cb is not None and not callable(start_span_cb):
            raise ValueError('start_span_cb is not callable')

        self._tracer_obj = tracer
        self._trace_all = trace_all
        self._current_spans = {}
        self._start_span_cb = start_span_cb

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
        return self._current_spans.get(request, None)

    def trace(self, *attributes):
        """
        Function decorator that traces functions
        NOTE: Must be placed after the @view_config decorator
        @param attributes any number of pyramid.request.Request attributes
        (strings) to be set as tags on the created span
        """
        def decorator(view_func):
            if self._trace_all:
                return view_func

            # otherwise, execute the decorator
            def wrapper(request):
                self._apply_tracing(request, list(attributes))
                try:
                    r = view_func(request)
                except:
                    self._finish_tracing(request, error=True)
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
        span = None
        try:
            span_ctx = self._tracer.extract(opentracing.Format.HTTP_HEADERS,
                                            headers)
            span = self._tracer.start_span(operation_name=operation_name,
                                           child_of=span_ctx)
        except (opentracing.InvalidCarrierException,
                opentracing.SpanContextCorruptedException):
            span = self._tracer.start_span(operation_name=operation_name)

        # add span to current spans
        self._current_spans[request] = span

        # Standard tags.
        span.set_tag(tags.COMPONENT, 'pyramid')
        span.set_tag(tags.HTTP_METHOD, request.method)
        span.set_tag(tags.HTTP_URL, request.path_url)

        # log any traced attributes
        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    span.set_tag(attr, payload)

        # invoke the start span callback, if any
        self._call_start_span_cb(span, request)

        return span

    def _finish_tracing(self, request, error=False):
        span = self._current_spans.pop(request, None)
        if span is None:
            return

        if error:
            span.set_tag(tags.ERROR, True)
        else:
            span.set_tag(tags.HTTP_STATUS_CODE, request.response.status_code)

        if getattr(request, 'matched_route', None) is not None:
            span.set_tag('pyramid.route', request.matched_route.name)

        span.finish()

    def _call_start_span_cb(self, span, request):
        if self._start_span_cb is None:
            return

        try:
            self._start_span_cb(span, request)
        except Exception:
            # TODO - log the error to the Span?
            pass
