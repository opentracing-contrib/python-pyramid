import mock
import unittest
from pyramid import testing
from pyramid.tweens import INGRESS
import opentracing
from opentracing.ext import tags

from .tracing import PyramidTracing
from .tween_factory import includeme, opentracing_tween_factory


class TestPyramidTracing(unittest.TestCase):
    def test_ctor_default(self):
        tracing = PyramidTracing()
        self.assertEquals(tracing.tracer, opentracing.tracer, '#A0')
        self.assertEquals(tracing._tracer, tracing.tracer, '#A1')
        self.assertFalse(tracing._trace_all, '#A2')
        self.assertEqual({}, tracing._current_spans, '#A3')
        self.assertIsNone(tracing._start_span_cb, '#A4')

    def test_ctor_tracer(self):
        tracer = DummyTracer()
        tracing = PyramidTracing(tracer)
        self.assertEqual(tracing.tracer, tracer)

    def test_ctor_trace_all(self):
        tracing = PyramidTracing(DummyTracer(), trace_all=True)
        self.assertTrue(tracing._trace_all)

        tracing = PyramidTracing(DummyTracer(), trace_all=False)
        self.assertFalse(tracing._trace_all)

    def test_ctor_cb(self):
        def test_func(span, request):
            pass

        tracing = PyramidTracing(DummyTracer(), start_span_cb=test_func)
        self.assertEqual(test_func, tracing._start_span_cb, '#A0')

    def test_ctor_cb_error(self):
        with self.assertRaises(ValueError):
            PyramidTracing(DummyTracer(), start_span_cb=4)

    def test_get_span_none(self):
        tracing = PyramidTracing(DummyTracer())
        self.assertIsNone(tracing.get_span(DummyRequest()), '#A0')

    def test_get_span(self):
        tracing = PyramidTracing(DummyTracer())
        req = DummyRequest()
        tracing._apply_tracing(req, [])
        self.assertIsNotNone(tracing.get_span(req), '#B0')
        self.assertIsNone(tracing.get_span(DummyRequest()), '#B1')
        self.assertEqual(1, len(tracing._current_spans), '#B2')

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
        tracing = PyramidTracing(DummyTracer())
        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertEqual('testing_foo', span.operation_name)

    def test_apply_tracing_start_span_cb(self):
        def test_func(span, request):
            self.assertIsNotNone(request)
            span.set_operation_name('testing_name')

        tracing = PyramidTracing(DummyTracer(), start_span_cb=test_func)
        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertEqual('testing_name', span.operation_name)

    def test_apply_tracing_start_span_cb_exc(self):
        def error_cb(span, request):
            raise ValueError()

        tracing = PyramidTracing(DummyTracer(), start_span_cb=error_cb)
        req = DummyRequest()
        req.matched_route = DummyRoute('testing_foo')

        # error on the cb, but the instrumentation path stays fine.
        span = tracing._apply_tracing(req, [])
        self.assertFalse(span._is_finished)

        tracing._finish_tracing(req)
        self.assertTrue(span._is_finished)

    def test_apply_tracing_attrs(self):
        tracing = PyramidTracing(DummyTracer())
        req = DummyRequest()

        # Make sure a few tags are available since the start.
        span = tracing._apply_tracing(req, [])
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
        }, span._tags, 'A#0')
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, span._tags, '#A1')

        span = tracing._apply_tracing(req, ['dont', 'exist'])
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, span._tags, '#B0')

        span = tracing._apply_tracing(req, ['host', 'path'])
        tracing._finish_tracing(req)
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'host': 'example.com:80',
            'path': '/',
        }, span._tags, '#C0')

    def test_apply_tracing_child(self):
        tracing = PyramidTracing(DummyTracer(returnContext=True))
        span = tracing._apply_tracing(DummyRequest(), [])
        self.assertIsNotNone(span.child_of, '#A0')

        tracing = PyramidTracing(DummyTracer(returnContext=False))
        span = tracing._apply_tracing(DummyRequest(), [])
        self.assertIsNone(span.child_of, '#B0')

    def test_apply_tracing_matched_route(self):
        tracing = PyramidTracing(DummyTracer())
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
        }, span._tags, '#A0')

    def test_finish_none(self):
        tracing = PyramidTracing(DummyTracer())
        tracing._finish_tracing(DummyRequest())

    def test_finish(self):
        tracing = PyramidTracing(DummyTracer())
        req = DummyRequest()
        req.matched_route = DummyRoute()

        span = tracing._apply_tracing(req, [])
        tracing._finish_tracing(req)
        self.assertTrue(span._is_finished)

    def test_decorator(self):
        tracer = DummyTracer()
        tracing = PyramidTracing(tracer)

        @tracing.trace()
        def sample_func(req):
            tracing.get_span(req).set_tag(tags.COMPONENT, 'pyramid-custom')
            return 'Hello, Tests!'

        sample_func(DummyRequest())
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid-custom',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, tracer.spans[0]._tags, '#A1')
        self.assertEqual(True, tracer.spans[0]._is_finished, '#A2')

    def test_decorator_attributes(self):
        tracer = DummyTracer()
        tracing = PyramidTracing(tracer)

        @tracing.trace('method', 'dontexist')
        def sample_func(req):
            return 'Hello, Tests!'

        sample_func(DummyRequest())
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'method': 'GET',
        }, tracer.spans[0]._tags, '#A1')
        self.assertEqual(True, tracer.spans[0]._is_finished, '#A2')

    def test_decorator_exc(self):
        tracer = DummyTracer()
        tracing = PyramidTracing(tracer)
        req = DummyRequest()

        @tracing.trace('method')
        def sample_func(req):
            raise ValueError('Testing exception')

        try:
            sample_func(req)
        except ValueError:
            pass

        self.assertIsNone(tracing.get_span(req), '#A0')
        self.assertEqual(1, len(tracer.spans), '#A1')
        self.assertTrue(tracer.spans[0]._is_finished, '#A2')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.ERROR: True,
            'method': 'GET',
        }, tracer.spans[0]._tags, '#A2')


def tracer_callable(**settings):
    tracer = DummyTracer()
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
        self.assertEqual(1, len(tracer.spans), '#A0')

        # Assert the settings information was properly
        # propagated.
        self.assertEqual('MyComponent', tracer.component_name, '#B0')

    def test_trace_all(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer

        self._call(registry=registry)
        self.assertEqual(1, len(tracer.spans), '#A0')

        tracer._clear()
        registry.settings['ot.trace_all'] = False
        self._call(registry=registry)
        self.assertEqual(0, len(tracer.spans), '#B0')

        tracer._clear()
        registry.settings['ot.trace_all'] = True
        self._call(registry=registry)
        self.assertEqual(1, len(tracer.spans), '#C0')

    def test_trace_all_as_str(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer

        registry.settings['ot.trace_all'] = 'false'
        self._call(registry=registry)
        self.assertEqual(0, len(tracer.spans), '#A0')

        registry.settings['ot.trace_all'] = 'true'
        self._call(registry=registry)
        self.assertEqual(1, len(tracer.spans), '#A0')

    def test_tracer_property(self):
        registry = DummyRegistry()
        self._call(registry=registry)
        self.assertIsNotNone(registry.settings.get('ot.tracing'))

        with mock.patch('opentracing.tracer'):
            self.assertTrue(registry.settings.get('ot.tracing').tracer,
                            opentracing.tracer)

    def test_trace_operation_name(self):
        registry = DummyRegistry()
        tracer = DummyTracer()

        registry.settings['ot.tracer'] = tracer
        for i in range(1, 4):
            req = DummyRequest(path='/%s' % i,
                               path_qs='/%s?q=123',
                               params={'q': '123'})
            req.matched_route = DummyRoute(str(i))
            self._call(registry=registry, request=req)

        # We should be taking the *path* as operation_name
        self.assertEqual(3, len(tracer.spans), '#A0')
        self.assertEqual(list(map(lambda x: x.operation_name, tracer.spans)),
                         ['1', '2', '3'])

    def test_trace_start_span_cb(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        cb_name = 'pyramid_opentracing.tests.start_span_cb'

        registry.settings['ot.tracer'] = tracer
        registry.settings['ot.start_span_cb'] = cb_name

        for i in range(1, 4):
            req = DummyRequest(path='/%s' % i)
            req.matched_route = DummyRoute(str(i))
            self._call(registry=registry, request=req)

        # 'tests.start_span_cb' sets operation_name to 'testing_name'
        self.assertEqual(3, len(tracer.spans), '#A0')
        self.assertTrue(all(map(lambda x: x.operation_name == 'testing_name',
                                tracer.spans)))

    def test_trace_start_span_cb2(self):
        registry = DummyRegistry()
        tracer = DummyTracer()

        registry.settings['ot.tracer'] = tracer
        registry.settings['ot.start_span_cb'] = start_span_cb

        for i in range(1, 4):
            req = DummyRequest(path='/%s' % i)
            req.matched_route = DummyRoute(str(i))
            self._call(registry=registry, request=req)

        # 'tests.start_span_cb' sets operation_name to 'testing_name'
        self.assertEqual(3, len(tracer.spans), '#A0')
        self.assertTrue(all(map(lambda x: x.operation_name == 'testing_name',
                                tracer.spans)))

    def test_trace_matched_route(self):
        registry = DummyRegistry()
        tracer = DummyTracer()

        registry.settings['ot.tracer'] = tracer
        req = DummyRequest()
        req.matched_route = DummyRoute('foo')
        self._call(registry=registry, request=req)
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'pyramid.route': 'foo',
        }, tracer.spans[0]._tags, '#A1')

    def test_trace_operation_name_matched_none(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer

        # Requests without url matching should be traced too.
        req = DummyRequest()
        req.matched_route = None
        self._call(registry=registry, request=req)
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertEqual('GET', tracer.spans[0].operation_name, '#A1')
        self.assertTrue(tracer.spans[0]._is_finished, '#A2')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, tracer.spans[0]._tags, '#A3')

    def test_trace_tags(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer

        registry.settings['ot.traced_attributes'] = [
                'path',
                'method',
                'dontexist'
        ]
        self._call(registry=registry, request=DummyRequest(path='/one'))
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'path': '/one',
            'method': 'GET',
        }, tracer.spans[0]._tags, '#A0')

        tracer._clear()
        registry.settings['ot.traced_attributes'] = []
        self._call(registry=registry, request=DummyRequest(path='/one'))
        self.assertEqual(1, len(tracer.spans), '#B0')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
        }, tracer.spans[0]._tags, '#B1')

    def test_trace_tags_as_str(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer

        registry.settings['ot.traced_attributes'] = 'path\nmethod\ndontexist'
        self._call(registry=registry, request=DummyRequest(path='/one'))
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'path': '/one',
            'method': 'GET',
        }, tracer.spans[0]._tags, '#A0')

    def test_trace_tags_override(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer
        registry.settings['ot.traced_attributes'] = ['method']

        def handler(req):
            span = registry.settings['ot.tracing'].get_span(req)
            span.set_tag('component', 'pyramid-custom')
            span.set_tag('method', 'POST')

        self._call(handler=handler, registry=registry)
        self.assertEqual({
            tags.COMPONENT: 'pyramid-custom',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.HTTP_STATUS_CODE: 200,
            'method': 'POST',
        }, tracer.spans[0]._tags, '#A0')

    def test_trace_finished(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        registry.settings['ot.tracer'] = tracer

        req = DummyRequest()
        req.matched_route = DummyRoute()
        self._call(registry=registry, request=req)
        self.assertEqual(1, len(tracer.spans), '#A0')
        self.assertTrue(tracer.spans[0]._is_finished, '#A1')

    def test_trace_exc(self):
        registry = DummyRegistry()
        tracer = DummyTracer()
        req = DummyRequest()
        registry.settings['ot.tracer'] = tracer

        def handler(req):
            raise ValueError('Testing error')

        try:
            self._call(registry=registry, handler=handler, request=req)
        except ValueError:
            pass

        self.assertIsNone(registry.settings['ot.tracing'].get_span(req), '#A0')
        self.assertEqual(1, len(tracer.spans), '#A1')
        self.assertTrue(tracer.spans[0]._is_finished, '#A2')
        self.assertEqual({
            tags.COMPONENT: 'pyramid',
            tags.HTTP_METHOD: 'GET',
            tags.HTTP_URL: 'http://example.com',
            tags.ERROR: True,
        }, tracer.spans[0]._tags, '#A3')


class TestIncludeme(unittest.TestCase):

    def test_it(self):
        config = DummyConfig()
        includeme(config)
        self.assertEqual(config.tweens, [(
            'pyramid_opentracing.opentracing_tween_factory',
            INGRESS,
            None
        )])


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

    def set_operation_name(self, operation_name):
        self.operation_name = operation_name
        return self

    def set_tag(self, name, value):
        self._tags[name] = value

    def finish(self):
        self._is_finished = True
