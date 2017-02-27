##################
Django Opentracing
##################

This package enables distributed tracing in Pyramid projects via `The OpenTracing Project`_. Once a production system contends with real concurrency or splits into many services, crucial (and formerly easy) tasks become difficult: user-facing latency optimization, root-cause analysis of backend errors, communication about distinct pieces of a now-distributed system, etc. Distributed tracing follows a request on its journey from inception to completion from mobile/browser all the way to the microservices.

Setting up Tracing
==================

In order to implement tracing in your system (for all the requests), add the following lines of code to your site's Configuration section to enable the tracing tweed:

.. code-block:: python

    # OpenTracing settings

    # if not included, defaults to False
    config.add_attributes(opentracing_trace_all=True)

    # defaults to []
    # only valid if 'opentracing_trace_all' == True
    config.add_attributes(opentracing_trace_attributes=['host', 'method', ...])

    # can be any valid underlying OpenTracing tracer implementation
    config.add_attributes(opentracing_base_tracer=...)

    # enable the tween
    config.include('pyramid_opentracing')

