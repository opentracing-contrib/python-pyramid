import opentracing


def default_operation_name_func(request):
    """
    @param request
    Returns the request matched route name, if any, as
    operation name, else returning the request's method.
    """
    if getattr(request, 'matched_route', None) is None:
        return request.method

    return request.matched_route.name

# Ported from the Django library:
# https://github.com/opentracing-contrib/python-django
class PyramidTracer(object):
    '''
    @param tracer the OpenTracing tracer to be used
    to trace requests using this PyramidTracer
    '''
    def __init__(self, tracer, trace_all=False, operation_name_func=None):
        self._tracer = tracer
        self._trace_all = trace_all
        self._current_spans = {}
        self._operation_name_func = operation_name_func

        if self._operation_name_func is None:
            self._operation_name_func = default_operation_name_func

    def get_span(self, request):
        '''
        @param request 
        Returns the span tracing this request
        '''
        return self._current_spans.get(request, None)

    def trace(self, *attributes):
        '''
        Function decorator that traces functions
        NOTE: Must be placed after the @view_config decorator
        @param attributes any number of pyramid.request.Request attributes
        (strings) to be set as tags on the created span
        '''
        def decorator(view_func):
            if self._trace_all:
                return view_func

            # otherwise, execute the decorator
            def wrapper(request):
                span = self._apply_tracing(request, list(attributes))
                try:
                    r = view_func(request)
                except:
                    self._finish_tracing(request, error=True)
                    raise

                self._finish_tracing(request)
                return r

            return wrapper
        return decorator

    def _apply_tracing(self, request, attributes):
        '''
        Helper function to avoid rewriting for middleware and decorator.
        Returns a new span from the request with logged attributes and 
        correct operation name from the view_func.
        '''
        headers = request.headers

        operation_name = self._operation_name_func(request)

        # start new span from trace info
        span = None
        try:
            span_ctx = self._tracer.extract(opentracing.Format.HTTP_HEADERS, headers)
            span = self._tracer.start_span(operation_name=operation_name, child_of=span_ctx)
        except (opentracing.InvalidCarrierException, opentracing.SpanContextCorruptedException) as e:
            span = self._tracer.start_span(operation_name=operation_name)

        # add span to current spans 
        self._current_spans[request] = span

        # log any traced attributes
        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    span.set_tag(attr, payload)

        # Put the component tag before finishing, so the user can override it.
        span.set_tag('component', 'pyramid')

        return span

    def _finish_tracing(self, request, error=False):
        span = self._current_spans.pop(request, None)     
        if span is None:
            return

        if error:
            span.set_tag('error', 'true')
        if getattr(request, 'matched_route', None) is not None:
            span.set_tag('pyramid.route', request.matched_route.name)

        span.finish()

