import mock
import unittest
from pyramid import testing
from pyramid.tweens import INGRESS
import opentracing
from opentracing.ext import tags
from opentracing.mocktracer import MockTracer

from .tracing import PyramidTracing
from .tween_factory import includeme, opentracing_tween_factory


class TestPyramidTracing(unittest.TestCase):
    def test_ctor_default(self):
        tracing = PyramidTracing()
        self.assertEquals(tracing.tracer, opentracing.tracer, '#A0')
        self.assertEquals(tracing._tracer, tracing.tracer, '#A1')
        self.assertFalse(tracing._trace_all, '#A2')
        self.assertIsNone(tracing._start_span_cb, '#A4')

    def test_ctor_tracer(self):
        tracer = MockTracer()
        tracing = PyramidTracing(tracer)
        self.assertEqual(tracing.tracer, tracer)

    def test_ctor_trace_all(self):
        tracing = PyramidTracing(MockTracer(), trace_all=True)
        self.assertTrue(tracing._trace_all)

        tracing = PyramidTracing(MockTracer(), trace_all=False)
        self.assertFalse(tracing._trace_all)

    def test_ctor_cb(self):
        def test_func(span, request):
            pass

        tracing = PyramidTracing(MockTracer(), start_span_cb=test_func)
        self.assertEqual(test_func, tracing._start_span_cb, '#A0')

    def test_ctor_cb_error(self):
        with self.assertRaises(ValueError):
            PyramidTracing(MockTracer(), start_span_cb=4)

    def test_get_span_none(self):
        tracing = PyramidTracing(MockTracer())
        self.assertIsNone(tracing.get_span(DummyRequest()), '#A0')

    def test_get_span(self):
        tracing = PyramidTracing(MockTracer())
        req = DummyRequest()

        tracing._apply_tracing(req, [])
        self.assertIsNotNone(tracing.get_span(req), '#B0')

        tracing._finish_tracing(req)
        self.assertIsNone(tracing.get_span(req), '#B2')

    def test_active_span(self):
        tracing = PyramidTracing(MockTracer())
        req = DummyRequest()

        tracing._apply_tracing(req, [])
        self.assertIsNotNone(tracing.tracer.active_span)
        self.assertEqual(tracing.tracer.active_span, tracing.get_span(req))

        tracing._finish_tracing(req)
        self.assertIsNone(tracing.tracer.active_span)

    def test_tracer(self):
        tracing = PyramidTracing()
        self.assertEqual(tracing.tracer, opentracing.tracer)

        with mock.patch('opentracing.tracer') as tracer:
            self.assertEqual(tracing.tracer, tracer)

    def test_apply_tracing_invalid(self):
        tracing = PyramidTracing(
            DummyTracer(opentracing.InvalidCarrierException())
        )
        tracing._apply_tracing(DummyRequest(), [])

    def test_apply_tracing_corrupted(self):
        tracing = PyramidTracing(
            DummyTracer(opentracing.SpanContextCorruptedException())
        )
        tracing._apply_tracing(DummyRequest(), [])

    def test_apply_tracing_operation_name(self):
        tracing = PyramidTracing(MockTracer())
        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertEqual('testing_foo', span.operation_name)

    def test_apply_tracing_start_span_cb(self):
        def test_func(span, request):
            self.assertIsNotNone(request)
            span.set_operation_name('testing_name')

        tracing = PyramidTracing(MockTracer(), start_span_cb=test_func)
        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertEqual('testing_name', span.operation_name)

    def test_apply_tracing_start_span_cb_exc(self):
        def error_cb(span, request):
            raise ValueError()

        tracing = PyramidTracing(MockTracer(), start_span_cb=error_cb)
        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')

        # error on the cb, but the instrumentation path stays fine.
        span = tracing._apply_tracing(req, [])
        self.assertFalse(span.finished)
        self.assertIsNotNone(tracing.tracer.active_span)

        tracing._finish_tracing(req)
        self.assertTrue(span.finished)
        self.assertIsNone(tracing.tracer.active_span)

    def test_apply_tracing_attrs(self):
        tracing = PyramidTracing(MockTracer())
        req = DummyRequest()

        # Make sure a few tags are available since the start.
        span = tracing._apply_tracing(req, [])
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
        }, span.tags, 'A#0')
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, span.tags, '#A1')

        span = tracing._apply_tracing(req, ['dont', 'exist'])
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, span.tags, '#B0')

        span = tracing._apply_tracing(req, ['host', 'path'])
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'host': 'example.com:80',
            'path': '/',
        }, span.tags, '#C0')

    def test_apply_tracing_child(self):
        tracer = MockTracer()
        tracing = PyramidTracing(tracer)
        span = tracing._apply_tracing(DummyRequest(), [])
        self.assertIsNone(span.parent_id, '#A0')

        context = tracer.start_span('foo').context
        tracing = PyramidTracing(DummyTracer(context=context))
        span = tracing._apply_tracing(DummyRequest(), [])
        self.assertIsNotNone(span.parent_id, '#B0')

    def test_apply_tracing_matched_route(self):
        tracing = PyramidTracing(MockTracer())
        req = DummyRequest()
        req.matched_route = DummyRoute('foo')

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'pyramid.route': 'foo',
        }, span.tags, '#A0')

    def test_finish_none(self):
        tracing = PyramidTracing(MockTracer())
        tracing._finish_tracing(DummyRequest())

    def test_finish(self):
        tracing = PyramidTracing(MockTracer())
        req = DummyRequest()
        req.matched_route = DummyRoute()

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertTrue(span.finished)

    def test_decorator(self):
        tracer = MockTracer()
        tracing = PyramidTracing(tracer)

        @tracing.trace()
        def sample_func(req):
            tracing.get_span(req).set_tag(tags.COMPONENT, 'pyramid-custom')
            return 'Hello, Tests!'

        sample_func(DummyRequest())
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid-custom',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, spans[0].tags, '#A1')
        self.assertEqual(True, spans[0].finished, '#A2')

    def test_decorator_attributes(self):
        tracer = MockTracer()
        tracing = PyramidTracing(tracer)

        @tracing.trace('method', 'dontexist')
        def sample_func(req):
            return 'Hello, Tests!'

        sample_func(DummyRequest())
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'method': 'GET',
        }, spans[0].tags, '#A1')
        self.assertEqual(True, spans[0].finished, '#A2')

    def test_decorator_exc(self):
        tracer = MockTracer()
        tracing = PyramidTracing(tracer)
        req = DummyRequest()

        @tracing.trace('method')
        def sample_func(req):
            raise ValueError('Testing exception')

        try:
            sample_func(req)
        except ValueError:
            pass

        spans = tracer.finished_spans()
        self.assertIsNone(tracing.get_span(req), '#A0')
        self.assertEqual(1, len(spans), '#A1')
        self.assertTrue(spans[0].finished, '#A2')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.ERROR: True,
            'method': 'GET',
        }, spans[0].tags, '#A2')

        self.assertIsNone(tracing.tracer.active_span)


def tracer_callable(**settings):
    tracer = MockTracer()
    tracer.component_name = settings['component_name']
    return tracer


def start_span_cb(span, request):
    span.set_operation_name('testing_name')


class TestTweenFactory(unittest.TestCase):

    def setUp(self):
        self.request = DummyRequest()
        self.response = DummyResponse()

    def default_handler(self, req):
        return self.response

    def _call(self, handler=None, registry=None, request=None):
        if not handler:
            handler = self.default_handler
        if not registry:
            registry = DummyRegistry()
        if not request:
            request = self.request

        factory = opentracing_tween_factory(handler, registry)
        return factory(request)

    def test_default(self):
        registry = DummyRegistry()
        self._call(registry=registry)
        self.assertIsNotNone(registry.settings.get('ot.tracing'), '#A0')
        self.assertTrue(registry.settings.get('ot.tracing')._trace_all, '#A1')
        self.assertTrue(registry.settings.get('ot.tracing').tracer,
                        opentracing.tracer)

    def test_tracer_callable(self):
        tracer_func = 'pyramid_opentracing.tests.tracer_callable'
        registry = DummyRegistry()
        registry.settings['component_name'] = 'MyComponent'
        registry.settings['ot.tracer_callable'] = tracer_func
        self._call(registry=registry)

        tracer = registry.settings['ot.tracing'].tracer
        self.assertEqual(1, len(tracer.finished_spans()), '#A0')
        self.assertIsNone(tracer.active_span)

        # Assert the settings information was properly
        # propagated.
        self.assertEqual('MyComponent', tracer.component_name, '#B0')

    def test_trace_all(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer

        self._call(registry=registry)
        self.assertEqual(1, len(tracer.finished_spans()), '#A0')

        tracer.reset()
        registry.settings['ot.trace_all'] = False
        self._call(registry=registry)
        self.assertEqual(0, len(tracer.finished_spans()), '#B0')

        tracer.reset()
        registry.settings['ot.trace_all'] = True
        self._call(registry=registry)
        self.assertEqual(1, len(tracer.finished_spans()), '#C0')

    def test_trace_all_as_str(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer

        registry.settings['ot.trace_all'] = 'false'
        self._call(registry=registry)
        self.assertEqual(0, len(tracer.finished_spans()), '#A0')

        registry.settings['ot.trace_all'] = 'true'
        self._call(registry=registry)
        self.assertEqual(1, len(tracer.finished_spans()), '#A0')

    def test_tracer_property(self):
        registry = DummyRegistry()
        self._call(registry=registry)
        self.assertIsNotNone(registry.settings.get('ot.tracing'))

        with mock.patch('opentracing.tracer'):
            self.assertTrue(registry.settings.get('ot.tracing').tracer,
                            opentracing.tracer)

    def test_trace_operation_name(self):
        registry = DummyRegistry()
        tracer = MockTracer()

        registry.settings['ot.tracer'] = tracer
        for i in range(1, 4):
            req = DummyRequest(path='/%s' % i,
                               path_qs='/%s?q=123',
                               params={'q': '123'})
            req.matched_route = DummyRoute(str(i))
            self._call(registry=registry, request=req)

        # We should be taking the *path* as operation_name
        spans = tracer.finished_spans()
        self.assertEqual(3, len(spans), '#A0')
        self.assertEqual(list(map(lambda x: x.operation_name, spans)),
                         ['1', '2', '3'])

    def test_trace_start_span_cb(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        cb_name = 'pyramid_opentracing.tests.start_span_cb'

        registry.settings['ot.tracer'] = tracer
        registry.settings['ot.start_span_cb'] = cb_name

        for i in range(1, 4):
            req = DummyRequest(path='/%s' % i)
            req.matched_route = DummyRoute(str(i))
            self._call(registry=registry, request=req)

        # 'tests.start_span_cb' sets operation_name to 'testing_name'
        spans = tracer.finished_spans()
        self.assertEqual(3, len(spans), '#A0')
        self.assertTrue(all(map(lambda x: x.operation_name == 'testing_name',
                                spans)))

    def test_trace_start_span_cb2(self):
        registry = DummyRegistry()
        tracer = MockTracer()

        registry.settings['ot.tracer'] = tracer
        registry.settings['ot.start_span_cb'] = start_span_cb

        for i in range(1, 4):
            req = DummyRequest(path='/%s' % i)
            req.matched_route = DummyRoute(str(i))
            self._call(registry=registry, request=req)

        # 'tests.start_span_cb' sets operation_name to 'testing_name'
        spans = tracer.finished_spans()
        self.assertEqual(3, len(spans), '#A0')
        self.assertTrue(all(map(lambda x: x.operation_name == 'testing_name',
                                spans)))

    def test_trace_matched_route(self):
        registry = DummyRegistry()
        tracer = MockTracer()

        registry.settings['ot.tracer'] = tracer
        req = DummyRequest()
        req.matched_route = DummyRoute('foo')
        self._call(registry=registry, request=req)

        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'pyramid.route': 'foo',
        }, spans[0].tags, '#A1')

    def test_trace_operation_name_matched_none(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer

        # Requests without url matching should be traced too.
        req = DummyRequest()
        req.matched_route = None
        self._call(registry=registry, request=req)

        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertEqual('GET', spans[0].operation_name, '#A1')
        self.assertTrue(spans[0].finished, '#A2')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, spans[0].tags, '#A3')

    def test_tracetags(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer

        registry.settings['ot.traced_attributes'] = [
                'path',
                'method',
                'dontexist'
        ]
        self._call(registry=registry, request=DummyRequest(path='/one'))
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'path': '/one',
            'method': 'GET',
        }, spans[0].tags, '#A1')

        tracer.reset()
        registry.settings['ot.traced_attributes'] = []
        self._call(registry=registry, request=DummyRequest(path='/one'))
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#B0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, spans[0].tags, '#B1')

    def test_tracetags_as_str(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer

        registry.settings['ot.traced_attributes'] = 'path\nmethod\ndontexist'
        self._call(registry=registry, request=DummyRequest(path='/one'))
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'path': '/one',
            'method': 'GET',
        }, spans[0].tags, '#A1')

    def test_tracetags_override(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer
        registry.settings['ot.traced_attributes'] = ['method']

        def handler(req):
            span = registry.settings['ot.tracing'].get_span(req)
            span.set_tag('component', 'pyramid-custom')
            span.set_tag('method', 'POST')

        self._call(handler=handler, registry=registry)
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans))
        self.assertEqual({
            tags.COMPONENT: 'pyramid-custom',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'method': 'POST',
        }, spans[0].tags, '#A0')

    def test_trace_finished(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        registry.settings['ot.tracer'] = tracer

        req = DummyRequest()
        req.matched_route = DummyRoute()
        self._call(registry=registry, request=req)

        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A0')
        self.assertTrue(spans[0].finished, '#A1')

    def test_trace_exc(self):
        registry = DummyRegistry()
        tracer = MockTracer()
        req = DummyRequest()
        registry.settings['ot.tracer'] = tracer

        def handler(req):
            raise ValueError('Testing error')

        try:
            self._call(registry=registry, handler=handler, request=req)
        except ValueError:
            pass

        self.assertIsNone(registry.settings['ot.tracing'].get_span(req), '#A0')
        spans = tracer.finished_spans()
        self.assertEqual(1, len(spans), '#A1')
        self.assertTrue(spans[0].finished, '#A2')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.ERROR: True,
        }, spans[0].tags, '#A3')

        self.assertIsNone(registry.settings['ot.tracing'].tracer.active_span)


class TestIncludeme(unittest.TestCase):

    def test_it(self):
        config = DummyConfig()
        includeme(config)
        self.assertEqual(config.tweens, [(
            'pyramid_opentracing.opentracing_tween_factory',
            INGRESS,
            None
        )])


class DummyTracer(MockTracer):
    def __init__(self, excToThrow=None, context=None):
        super(DummyTracer, self).__init__()
        self.excToThrow = excToThrow
        self.context = context

    def extract(self, f, headers):
        if self.excToThrow:
            raise self.excToThrow

        return self.context


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
