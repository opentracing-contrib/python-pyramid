import unittest
from pyramid import testing
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
        tracer = PyramidTracer(DummyTracer(opentracing.SpanContextCorruptedException()))
        span = tracer._apply_tracing(DummyRequest(), [])
        self.assertEqual('/', span.operation_name)

    def test_apply_tracing_attrs(self):
        tracer = PyramidTracer(DummyTracer())
        req = DummyRequest()

        span = tracer._apply_tracing(req, [])
        self.assertEqual({}, span._tags, '#A0')

        span = tracer._apply_tracing(req, ['dont', 'exist'])
        self.assertEqual({}, span._tags, '#B0')

        span = tracer._apply_tracing(req, ['host', 'path'])
        self.assertEqual({'host': 'example.com:80', 'path': '/'}, span._tags, '#C0')

    def test_finish_none(self):
        tracer = PyramidTracer(DummyTracer())
        tracer._finish_tracing(DummyRequest())

    def test_finish(self):
        tracer = PyramidTracer(DummyTracer())
        req = DummyRequest()
        span = tracer._apply_tracing(req, [])
        tracer._finish_tracing(req)
        self.assertTrue(span._is_finished)

class TestTweenFactory(unittest.TestCase):

    def setUp(self):
        self.request = DummyRequest()
        self.response = DummyResponse()
        self.registry = DummyRegistry()

    def test_it(self):
        handler = lambda x: self.response
        factory = opentracing_tween_factory(handler, self.registry)

        res = factory(self.request)
        self.assertIsNotNone(self.registry.settings.get('opentracing_tracer'))

class TestIncludeme(unittest.TestCase):

    def test_it(self):
        config = DummyConfig()
        includeme(config)
        self.assertEqual([('pyramid_opentracing.opentracing_tween_factory', None, None)], config.tweens, '#A0')

class DummyTracer(object):
    def __init__(self, excToThrow=None):
        super(DummyTracer, self).__init__()
        self.excToThrow = excToThrow

    def extract(self, f, headers):
        if self.excToThrow:
            raise self.excToThrow

        return DummyContext()

    def start_span(self, operation_name, child_of=None):
        return DummySpan(operation_name, child_of=child_of)

class DummyRegistry(object):
    def __init__(self, settings={}):
        self.settings = settings

class DummyConfig(object):
    def __init__(self):
        self.tweens = []

    def add_tween(self, x, under=None, over=None):
        self.tweens.append((x, under, over))

class DummyRequest(testing.DummyRequest):
    def __init__(self, *args, **kwargs):
        super(DummyRequest, self).__init__(*args, **kwargs)

class DummyResponse(object):
    def __init__(self, headers={}):
        self.headers = headers

class DummyContext(object):
    pass

class DummySpan(object):
    def __init__(self, operation_name, child_of):
        super(DummySpan, self).__init__()
        self.operation_name = operation_name
        self.child_of = child_of
        self._tags = {}

    def set_tag(self, name, value):
        self._tags[name] = value

    def finish(self):
        self._is_finished = True

