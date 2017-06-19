###################
Pyramid Opentracing
###################

This package enables distributed tracing in Pyramid projects via `The OpenTracing Project`_. Once a production system contends with real concurrency or splits into many services, crucial (and formerly easy) tasks become difficult: user-facing latency optimization, root-cause analysis of backend errors, communication about distinct pieces of a now-distributed system, etc. Distributed tracing follows a request on its journey from inception to completion from mobile/browser all the way to the microservices.

As core services and libraries adopt OpenTracing, the application builder is no longer burdened with the task of adding basic tracing instrumentation to their own code. In this way, developers can build their applications with the tools they prefer and benefit from built-in tracing instrumentation. OpenTracing implementations exist for major distributed tracing systems and can be bound or swapped with a one-line configuration change.

If you want to learn more about the underlying python API, visit the python `source code`_.

.. _The OpenTracing Project: http://opentracing.io/
.. _source code: https://github.com/opentracing/opentracing-python

Installation
============

Run the following command::

    $ pip install pyramid_opentracing

Setting up Tracing for All Requests
===================================

In order to implement tracing in your system (for all the requests), add the following lines of code to your site's Configuration section to enable the tracing tween:

.. code-block:: python

    # OpenTracing settings

    # if not included, defaults to False
    config.add_attributes({'ot.trace_all': True})

    # defaults to []
    # only valid if 'opentracing_trace_all' == True
    config.add_attributes({'ot.traced_attributes': ['host', 'method', ...]})

    # a module-level function that returns the operation name for a request object.
    # defaults to the matched route name or request's method if none.
    config.add_attributes({'ot.operation_name_func': 'my_main_module.get_operation_name_func'})

    # One valid underlying OpenTracing implementation as
    # one either one of these two values:

    # 1. A tracer object itself.
    config.add_attributes({'ot.base_tracer': ...})

    # 2. Or a module-level function that returns a tracer object,
    #    receiving the settings, such as: create_tracer(**settings)
    config.add_attributes({'ot.base_tracer_func', 'my_main_module.utils.create_tracer')

    # enable the tween
    config.include('pyramid_opentracing')

Alternatively, you can configure the tween through an INI file:

.. code-block:: ini

    [app:myapp]
    ot.trace_all = true
    ot.operation_name_func = my_main_module.get_operation_name_func
    ot.traced_attributes = host
                          method
    ot.base_tracer_func = my_main_module.utils.get_tracer
    pyramid.includes = pyramid_opentracing

Once the tween has been included, an instance of PyramidTracer will be exist in registry.settings['ot.tracer'] for any further reference.

**Note:** Valid request attributes to trace are listed [here](http://docs.pylonsproject.org/projects/pyramid/en/latest/api/request.html#pyramid.request.Request). When you trace an attribute, this means that created spans will have tags with the attribute name and the request's value.

Tracing Individual Requests
===========================

If you don't want to trace all requests to your site, you can use function decorators to trace individual view functions. This can be done by managing a globally unique PyramidTracer object yourself, and then adding the following lines of code to  any file that has view functions:

.. code-block:: python

    # get_tracer() should return a globally-unique PyramidTracer object.
    from my_tracer_mod import get_tracer

    tracer = get_tracer()

    # put the decorator after @view_config, if used
    @tracer.trace(optional_args)
    def some_view_func(request):
        ... #do some stuff

This tracing method doesn't use the tween, so there's no need to include that one.

The optional arguments allow for tracing of request attributes. For example, if you want to trace metadata, you could pass in `@tracer.trace('headers')` and request.headers would be set as a tag on all spans for this view function.

Examples
========

Here is an `tween example`_ of a Pyramid application that uses the Pyramid tween to log all
requests:

.. _tween example: https://github.com/carlosalberto/python-pyramid/tree/master/example/tween-example/main.py

Here is an `client server example`_ of an application that acts as both a client and server,
with a manually managed tracer (you will need to install the `waitress` module).

.. _client server example: https://github.com/carlosalberto/python-pyramid/tree/master/example/client-server/main.py

Other examples are included under the examples directrory.

Further Information
===================

If you’re interested in learning more about the OpenTracing standard, please visit `opentracing.io`_ or `join the mailing list`_. If you would like to implement OpenTracing in your project and need help, feel free to send us a note at `community@opentracing.io`_.

.. _opentracing.io: http://opentracing.io/
.. _join the mailing list: http://opentracing.us13.list-manage.com/subscribe?u=180afe03860541dae59e84153&id=19117aa6cd
.. _community@opentracing.io: community@opentracing.io

