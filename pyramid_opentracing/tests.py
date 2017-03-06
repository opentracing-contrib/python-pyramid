import unittest
from pyramid import testing
from pyramid.tweens import INGRESS
import opentracing

from tracer import PyramidTracer
from tween_factory import includeme, opentracing_tween_factory

class TestPyramidTracer(unittest.TestCase):
    def test_ctor_default(self):
        tracer = PyramidTracer(DummyTracer())
        self.assertIsNotNone(tracer._tracer, '#A0')
        self.assertFalse(tracer._trace_all, '#A1')
        self.assertEqual({}, tracer._current_spans, '#A2')

    def test_ctor(self):
        tracer = PyramidTracer(DummyTracer(), trace_all=True)
        self.assertTrue(tracer._trace_all, '#A0')

        tracer = PyramidTracer(DummyTracer(), trace_all=False)
        self.assertFalse(tracer._trace_all, '#B0')

    def test_get_span_none(self):
        tracer = PyramidTracer(DummyTracer())
        self.assertIsNone(tracer.get_span(DummyRequest()), '#A0')

    def test_get_span(self):
        tracer = PyramidTracer(DummyTracer())
        req = DummyRequest()
        tracer._apply_tracing(req, [])
        self.assertIsNotNone(tracer.get_span(req), '#B0')
        self.assertIsNone(tracer.get_span(DummyRequest()), '#B1')
        self.assertEqual(1, len(tracer._current_spans), '#B2')

    def test_apply_tracing_invalid(self):
        tracer = PyramidTracer(DummyTracer(opentracing.InvalidCarrierException()))
        tracer._apply_tracing(DummyRequest(), [])

    def test_apply_tracing_corrupted(self):
        tracer = PyramidTracer(DummyTracer(opentracing.SpanContextCorruptedException()))
        tracer._apply_tracing(DummyRequest(), [])

    def test_apply_tracing_operation(self):
        tracer = PyramidTracer(DummyTracer())
        span = tracer._apply_tracing(DummyRequest(), [])
        self.assertEqual('/', span.operation_name)

    def test_apply_tracing_operation_matched(self):
        tracer = PyramidTracer(DummyTracer())
        req = DummyRequest()

        span = tracer._apply_tracing(req, [])
        self.assertEqual('/', span.operation_name)

        req.matched_route = DummyRoute('testing_foo')
        tracer._finish_tracing(req)
        self.assertEqual('testing_foo', span.operation_name)

    def test_apply_tracing_attrs(self):
        tracer = PyramidTracer(DummyTracer())
        req = DummyRequest()

        span = tracer._apply_tracing(req, [])
        self.assertEqual({}, span._tags, '#A0')

        span = tracer._apply_tracing(req, ['dont', 'exist'])
        self.assertEqual({}, span._tags, '#B0')

        span = tracer._apply_tracing(req, ['host', 'path'])
        self.assertEqual({'host': 'example.com:80', 'path': '/'}, span._tags, '#C0')

    def test_apply_tracing_child(self):
        tracer = PyramidTracer(DummyTracer(returnContext=True))
        span = tracer._apply_tracing(DummyRequest(), [])
        self.assertIsNotNone(span.child_of, '#A0')

        tracer = PyramidTracer(DummyTracer(returnContext=False))
        span = tracer._apply_tracing(DummyRequest(), [])
        self.assertIsNone(span.child_of, '#B0')

    def test_finish_none(self):
        tracer = PyramidTracer(DummyTracer())
        tracer._finish_tracing(DummyRequest())

    def test_finish(self):
        tracer = PyramidTracer(DummyTracer())
        req = DummyRequest()
        req.matched_route = DummyRoute()

        span = tracer._apply_tracing(req, [])
        tracer._finish_tracing(req)
        self.assertTrue(span._is_finished)

    def test_decorator(self):
        base_tracer = DummyTracer()
        tracer = PyramidTracer(base_tracer)

        @tracer.trace()
        def sample_func(req):
            return "Hello, Tests!"

        req = DummyRequest()
        req.matched_route = DummyRoute()
        sample_func(req)
        self.assertEqual(1, len(base_tracer.spans), '#A0')
        self.assertEqual({}, base_tracer.spans[0]._tags, '#A1')
        self.assertEqual(True, base_tracer.spans[0]._is_finished, '#A2')

    def test_decorator_attributes(self):
        base_tracer = DummyTracer()
        tracer = PyramidTracer(base_tracer)

        @tracer.trace('method', 'dontexist')
        def sample_func(req):
            return "Hello, Tests!"

        req = DummyRequest()
        req.matched_route = DummyRoute()
        sample_func(req)
        self.assertEqual(1, len(base_tracer.spans), '#A0')
        self.assertEqual({'method': 'GET'}, base_tracer.spans[0]._tags, '#A1')
        self.assertEqual(True, base_tracer.spans[0]._is_finished, '#A2')

    def test_decorator_exc(self):
        base_tracer = DummyTracer()
        tracer = PyramidTracer(base_tracer)
        req = DummyRequest()
        req.matched_route = DummyRoute()

        @tracer.trace('method')
        def sample_func(req):
            raise ValueError('Testing exception')

        try:
            sample_func(req)
        except ValueError:
            pass

        self.assertIsNone(tracer.get_span(req), '#A0')
        self.assertEqual(1, len(base_tracer.spans), '#A1')
        self.assertTrue(base_tracer.spans[0]._is_finished, '#A2')

def base_tracer_func(**settings):
    tracer = DummyTracer()
    tracer.component_name = settings['component_name']
    return tracer

class TestTweenFactory(unittest.TestCase):

    def setUp(self):
        self.request = DummyRequest()
        self.response = DummyResponse()

    def _call(self, handler=None, registry=None, request=None):
        if not handler:
            handler = lambda req: self.response
        if not registry:
            registry = DummyRegistry()
        if not request:
            request = self.request

        factory = opentracing_tween_factory(handler, registry)
        return factory(request)

    def test_default(self):
        registry = DummyRegistry()
        res = self._call(registry=registry)
        self.assertIsNotNone(registry.settings.get('ot.tracer'), '#A0')
        self.assertFalse(registry.settings.get('ot.tracer')._trace_all, '#A1')

    def test_tracer_base_func(self):
        registry = DummyRegistry()
        registry.settings['component_name'] = 'MyComponent'
        registry.settings['ot.base_tracer_func'] = 'tests.base_tracer_func'
        registry.settings['ot.trace_all'] = True
        self._call(registry=registry)

        tracer = registry.settings['ot.tracer']._tracer
        self.assertEqual(1, len(tracer.spans), '#A0')

        # Assert the settings information was properly
        # propagated.
        self.assertEqual('MyComponent', tracer.component_name, '#B0')

    def test_trace_all(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer

        self._call(registry=registry)
        self.assertEqual(0, len(tracer.spans), '#A0')

        tracer._clear()
        registry.settings['ot.trace_all'] = True
        self._call(registry=registry)
        self.assertEqual(1, len(tracer.spans), '#B0')

        tracer._clear()
        registry.settings['ot.trace_all'] = False
        self._call(registry=registry)
        self.assertEqual(0, len(tracer.spans), '#C0')

    def test_trace_all_as_str(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer

        registry.settings['ot.trace_all'] = 'false'
        self._call(registry=registry)
        self.assertEqual(0, len(tracer.spans), '#A0')

        registry.settings['ot.trace_all'] = 'true'
        self._call(registry=registry)
        self.assertEqual(1, len(tracer.spans), '#A0')

    def test_trace_operation_name(self):
        registry = DummyRegistry()
        tracer = DummyTracer()

        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True
        for i in xrange(1, 4):
            self._call(registry=registry, request=DummyRequest(path='/%s' % i))
        self.assertEqual(3, len(tracer.spans), '#A0')
        self.assertEqual(['/1', '/2', '/3'], map(lambda x: x.operation_name, tracer.spans), '#A1')

    def test_trace_operation_name_matched(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True

        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')
        self._call(registry=registry, request=req)
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual('testing_foo', tracer.spans[0].operation_name, '#A1')

    def test_trace_operation_name_matched_none(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True

        # With a matched_route explicitly set to None, spans should be dropped
        # i.e. not finished
        req = DummyRequest()
        req.matched_route = None
        self._call(registry=registry, request=req)
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual('/', tracer.spans[0].operation_name, '#A1')
        self.assertFalse(tracer.spans[0]._is_finished, '#A2')

    def test_trace_tags(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True

        registry.settings['ot.traced_attributes'] = ['path', 'method', 'dontexist']
        self._call(registry=registry, request=DummyRequest(path='/one'))
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual({'path': '/one', 'method': 'GET'}, tracer.spans[0]._tags, '#A1')

        tracer._clear()
        registry.settings['ot.traced_attributes'] = []
        self._call(registry=registry, request=DummyRequest(path='/one'))
        self.assertEqual(1, len(tracer.spans), '#B0')
        self.assertEqual({}, tracer.spans[0]._tags, '#B1')

    def test_trace_tags_as_str(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True

        registry.settings['ot.traced_attributes'] = 'path\nmethod\ndontexist'
        self._call(registry=registry, request=DummyRequest(path='/one'))
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual({'path': '/one', 'method': 'GET'}, tracer.spans[0]._tags, '#A1')

    def test_trace_finished(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True

        req = DummyRequest()
        req.matched_route = DummyRoute()
        self._call(registry=registry, request=req)
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertTrue(tracer.spans[0]._is_finished, '#A1')

    def test_trace_exc(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        req = DummyRequest()
        req.matched_route = DummyRoute()
        registry.settings['ot.base_tracer'] = tracer
        registry.settings['ot.trace_all'] = True

        def handler(req):
            raise ValueError('Testing error')

        try:
            self._call(registry=registry, handler=handler, request=req)
        except ValueError:
            pass

        self.assertIsNone(registry.settings['ot.tracer'].get_span(req), '#A0')
        self.assertEqual(1, len(tracer.spans), '#A1')
        self.assertTrue(tracer.spans[0]._is_finished, '#A2')

class TestIncludeme(unittest.TestCase):

    def test_it(self):
        config = DummyConfig()
        includeme(config)
        self.assertEqual([('pyramid_opentracing.opentracing_tween_factory', INGRESS, None)], config.tweens, '#A0')

class DummyTracer(object):
    def __init__(self, excToThrow=None, returnContext=False):
        super(DummyTracer, self).__init__()
        self.excToThrow = excToThrow
        self.returnContext = returnContext
        self.spans = []

    def _clear(self):
        self.spans = []

    def extract(self, f, headers):
        if self.excToThrow:
            raise self.excToThrow
        if self.returnContext:
            return DummyContext()

        return None

    def start_span(self, operation_name, child_of=None):
        span = DummySpan(operation_name, child_of=child_of)
        self.spans.append(span)
        return span

class DummyRegistry(object):
    def __init__(self, settings=None):
        if not settings:
            settings = {}
        self.settings = settings

class DummyConfig(object):
    def __init__(self):
        self.tweens = []

    def add_tween(self, x, under=None, over=None):
        self.tweens.append((x, under, over))

class DummyRequest(testing.DummyRequest):
    def __init__(self, *args, **kwargs):
        super(DummyRequest, self).__init__(*args, **kwargs)

class DummyRoute(object):
    def __init__(self, name=''):
        self.name = name

class DummyResponse(object):
    def __init__(self, headers=None):
        if not headers:
            headers = {}
        self.headers = headers

class DummyContext(object):
    pass

class DummySpan(object):
    def __init__(self, operation_name, child_of):
        super(DummySpan, self).__init__()
        self.operation_name = operation_name
        self.child_of = child_of
        self._tags = {}
        self._is_finished = False

    def set_tag(self, name, value):
        self._tags[name] = value

    def finish(self):
        self._is_finished = True

